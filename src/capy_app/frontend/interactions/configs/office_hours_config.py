"""Configuration for office hours dropdown menus."""

TIME_SLOTS = [
    {"label": "8:00 AM", "value": "8:00 AM"},
    {"label": "9:00 AM", "value": "9:00 AM"},
    {"label": "10:00 AM", "value": "10:00 AM"},
    {"label": "11:00 AM", "value": "11:00 AM"},
    {"label": "12:00 PM", "value": "12:00 PM"},
    {"label": "1:00 PM", "value": "1:00 PM"},
    {"label": "2:00 PM", "value": "2:00 PM"},
    {"label": "3:00 PM", "value": "3:00 PM"},
    {"label": "4:00 PM", "value": "4:00 PM"},
    {"label": "5:00 PM", "value": "5:00 PM"},
    {"label": "6:00 PM", "value": "6:00 PM"},
    {"label": "7:00 PM", "value": "7:00 PM"},
    {"label": "8:00 PM", "value": "8:00 PM"},
    {"label": "9:00 PM", "value": "9:00 PM"},
    {"label": "10:00 PM", "value": "10:00 PM"},
    {"label": "11:00 PM", "value": "11:00 PM"},
]

OFFICE_HOURS_CONFIGS = {
    "first_half_week": {
        "ephemeral": True,
        "add_buttons": True,
        "dropdowns": [
            {
                "placeholder": "Sunday hours",
                "custom_id": "sunday",
                "min_values": 0,
                "max_values": len(TIME_SLOTS),
                "selections": TIME_SLOTS,
            },
            {
                "placeholder": "Monday hours",
                "custom_id": "monday",
                "min_values": 0,
                "max_values": len(TIME_SLOTS),
                "selections": TIME_SLOTS,
            },
            {
                "placeholder": "Tuesday hours",
                "custom_id": "tuesday",
                "min_values": 0,
                "max_values": len(TIME_SLOTS),
                "selections": TIME_SLOTS,
            },
            {
                "placeholder": "Wednesday hours",
                "custom_id": "wednesday",
                "min_values": 0,
                "max_values": len(TIME_SLOTS),
                "selections": TIME_SLOTS,
            },
        ],
    },
    "second_half_week": {
        "ephemeral": True,
        "add_buttons": True,
        "dropdowns": [
            {
                "placeholder": "Thursday hours",
                "custom_id": "thursday",
                "min_values": 0,
                "max_values": len(TIME_SLOTS),
                "selections": TIME_SLOTS,
            },
            {
                "placeholder": "Friday hours",
                "custom_id": "friday",
                "min_values": 0,
                "max_values": len(TIME_SLOTS),
                "selections": TIME_SLOTS,
            },
            {
                "placeholder": "Saturday hours",
                "custom_id": "saturday",
                "min_values": 0,
                "max_values": len(TIME_SLOTS),
                "selections": TIME_SLOTS,
            },
        ],
    },
}


def get_office_hours_config(defaults: dict = None) -> dict:
    """Get office hours config with optional default selections."""
    defaults = defaults or {}

    first_half_config = OFFICE_HOURS_CONFIGS["first_half_week"].copy()
    second_half_config = OFFICE_HOURS_CONFIGS["second_half_week"].copy()

    # Set default selections if provided
    if defaults:
        for dropdown in first_half_config["dropdowns"]:
            day = dropdown["custom_id"]
            if day in defaults:
                # Convert time strings to time value objects
                default_times = defaults[day]
                if default_times:
                    dropdown["default_values"] = default_times

        for dropdown in second_half_config["dropdowns"]:
            day = dropdown["custom_id"]
            if day in defaults:
                default_times = defaults[day]
                if default_times:
                    dropdown["default_values"] = default_times

    return {
        "first_half_week": first_half_config,
        "second_half_week": second_half_config,
    }
