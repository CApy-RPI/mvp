-- Roblox Logic Gates Puzzle Debug Analysis
-- Main Script (in ServerScriptService or similar)

local bulbs = {
	game.Workspace.LightsPuzzle.LightBulb1.Bulb,
	game.Workspace.LightsPuzzle.LightBulb2.Bulb,
	game.Workspace.LightsPuzzle.LightBulb3.Bulb,
	game.Workspace.LightsPuzzle.LightBulb4.Bulb,
	game.Workspace.LightsPuzzle.LightBulb5.Bulb,
}

local bulbColors = {
	Color3.fromRGB(0, 255, 0),    -- Green
	Color3.fromRGB(255, 0, 0),    -- Red
	Color3.fromRGB(0, 255, 255),  -- Cyan
	Color3.fromRGB(255, 0, 255),  -- Magenta
	Color3.fromRGB(255, 255, 0),  -- Yellow
}

local levers = {
	["Lever1"] = false,
	["Lever2"] = false,
	["Lever3"] = false,
	["Lever4"] = false,
	["Lever5"] = false,
}

local puzzleSolved = false

local function setBulbColorsToWhite()
	for _, bulb in ipairs(bulbs) do
		bulb.PointLight.Color = Color3.new(1, 1, 1)
		bulb.Color = Color3.new(1, 1, 1) -- Change mesh color to white
	end
end

local function setBulbColorsToSolved()
	for i, bulb in ipairs(bulbs) do
		bulb.PointLight.Color = bulbColors[i]
		bulb.Color = bulbColors[i] -- Change mesh color to solved color
	end
end

local function updateBulbs()
	bulbs[1].PointLight.Enabled = levers["Lever1"] and not levers["Lever2"]
	bulbs[2].PointLight.Enabled = levers["Lever1"] and not levers["Lever2"]
	bulbs[3].PointLight.Enabled = levers["Lever2"] or levers["Lever3"]
	bulbs[4].PointLight.Enabled = levers["Lever4"]
	bulbs[5].PointLight.Enabled = not levers["Lever5"]

	local allLit = true
	for _, bulb in ipairs(bulbs) do
		if not bulb.PointLight.Enabled then
			allLit = false
			break
		end
	end
	if allLit and not puzzleSolved then
		puzzleSolved = true
		print("Puzzle solved!")
		setBulbColorsToSolved()
		-- Add reward logic here
	elseif not allLit and puzzleSolved then
		puzzleSolved = false
		setBulbColorsToWhite()
	end
end

setBulbColorsToWhite()
updateBulbs()

-- DEBUG: Add connection with error handling
game.Workspace.LightsPuzzle.SwitchChanged.Event:Connect(function(leverName, state)
	print("Switch changed:", leverName, "to state:", state) -- DEBUG LINE
	levers[leverName] = state
	updateBulbs()
end)

-- Individual Lever Script (goes in each lever)
local leverModel = script.Parent
local promptPart = leverModel:FindFirstChildWhichIsA("Part") -- The part with the ProximityPrompt
local prompt = promptPart:FindFirstChildOfClass("ProximityPrompt")
local TweenService = game:GetService("TweenService")

-- DEBUG: Print lever name
print("Lever script loaded for:", leverModel.Name)

local hingePosition = leverModel.PrimaryPart.Position
local offAngle = math.rad(45)
local onAngle = math.rad(-45)
local isOn = false

leverModel:SetPrimaryPartCFrame(CFrame.new(hingePosition) * CFrame.Angles(offAngle, 0, 0))

prompt.Triggered:Connect(function(player)
	print("Prompt triggered for:", leverModel.Name, "by player:", player.Name) -- DEBUG LINE
	isOn = not isOn
	local targetAngle = isOn and onAngle or offAngle
	local targetCFrame = CFrame.new(hingePosition) * CFrame.Angles(targetAngle, 0, 0)
	leverModel:SetPrimaryPartCFrame(targetCFrame)
	
	-- DEBUG: Check if SwitchChanged exists
	local switchChanged = game.Workspace.LightsPuzzle:FindFirstChild("SwitchChanged")
	if switchChanged then
		print("Firing SwitchChanged for:", leverModel.Name, "state:", isOn) -- DEBUG LINE
		switchChanged:Fire(leverModel.Name, isOn)
	else
		print("ERROR: SwitchChanged not found!") -- DEBUG LINE
	end
end)

--[[
POTENTIAL ISSUES WITH LEVER5:

1. LEVER NAME MISMATCH:
   - Check if the Lever5 model is actually named "Lever5" (case-sensitive)
   - Use this debug code in the lever script:
   print("This lever's name is:", leverModel.Name)

2. MISSING PRIMARYPART:
   - Lever5 might not have a PrimaryPart set
   - Check if leverModel.PrimaryPart exists
   - Add this check: if not leverModel.PrimaryPart then print("No PrimaryPart for", leverModel.Name) end

3. MISSING PROXIMITYPRPOMPT:
   - Lever5 might not have a ProximityPrompt
   - Check if prompt exists
   - Add this check: if not prompt then print("No ProximityPrompt found for", leverModel.Name) end

4. SCRIPT NOT RUNNING:
   - The script inside Lever5 might not be running
   - Check if the script is enabled
   - Make sure the script is a ServerScript (not LocalScript)

5. SWITCHCHANGED EVENT MISSING:
   - Check if the SwitchChanged RemoteEvent/BindableEvent exists in LightsPuzzle
   - Make sure it's the correct type (RemoteEvent for client-server, BindableEvent for server-server)

6. HIERARCHY ISSUES:
   - Check if Lever5 is in the correct location in the workspace
   - Verify the part structure matches other working levers

DEBUGGING STEPS:
1. Add print statements to see if the lever script loads
2. Add print to see if prompt.Triggered fires
3. Check if SwitchChanged event fires
4. Verify lever name matches exactly
5. Check if PrimaryPart and ProximityPrompt exist
]]--
