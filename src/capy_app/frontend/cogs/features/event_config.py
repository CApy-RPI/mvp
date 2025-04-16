"""Configuration for event management."""

from discord import ButtonStyle, TextStyle

EVENT_CONFIG = {
    "event_modal": {
        "ephemeral": True,
        "modal": {
            "title": "Event Information",
            "fields": [
                {
                    "label": "Event Name",
                    "placeholder": "Enter the event name",
                    "required": True,
                    "custom_id": "event_name",
                },
                {
                    "label": "Event Description",
                    "placeholder": "Enter event description",
                    "required": True,
                    "custom_id": "event_description",
                    "style": TextStyle.paragraph,
                },
                {
                    "label": "Event Date",
                    "placeholder": "MM/DD/YY (e.g., 05/15/25)",
                    "required": True,
                    "custom_id": "event_date",
                },
                {
                    "label": "Event Time",
                    "placeholder": "HH:MM AM/PM (e.g., 03:30 PM)",
                    "required": True,
                    "custom_id": "event_time",
                },
                {
                    "label": "Event Location",
                    "placeholder": "Enter the event location",
                    "required": True,
                    "custom_id": "event_location",
                },
            ],
        },
    },
    "confirm_announce": {
        "ephemeral": True,
        "timeout": 60.0,
        "confirm_text": "Announce",
        "confirm_style": ButtonStyle.primary,
    },
    "announce_message": {
        "title": "Event Announcement",
        "color": 0x9B59B6,  # Purple
        "footer": "React with ✅ to attend, ❌ to decline, or ❔ for maybe."
    },
    "timezone_dropdown": {
        "ephemeral": True,
        "add_buttons": True,
        "placeholder": "Select Timezone",
        "dropdowns": [
            {
                "custom_id": "timezone_selection",
                "placeholder": "Select a timezone",
                "min_values": 1,
                "max_values": 1,
                "options": [
                    {"label": "Eastern (EDT/EST)", "value": "US/Eastern", "default": True},
                    {"label": "Central (CDT/CST)", "value": "US/Central"},
                    {"label": "Mountain (MDT/MST)", "value": "US/Mountain"},
                    {"label": "Pacific (PDT/PST)", "value": "US/Pacific"},
                    {"label": "Alaska (AKDT/AKST)", "value": "US/Alaska"},
                    {"label": "Hawaii (HST)", "value": "US/Hawaii"},
                    {"label": "UTC", "value": "UTC"},
                ],
            }
        ],
    },
}
