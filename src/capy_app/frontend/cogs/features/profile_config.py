"""Configuration for profile management."""

from discord import ButtonStyle

PROFILE_CONFIG = {
    "profile_modal": {
        "ephemeral": True,
        "modal": {
            "title": "Profile Information",
            "fields": [
                {
                    "label": "Preferred Name",
                    "placeholder": "Enter your preferred first and last name",
                    "required": True,
                    "custom_id": "preferred_name",
                },
                {
                    "label": "Student ID",
                    "placeholder": "Enter your student ID (e.g. 661234567)",
                    "required": True,
                    "min_length": 9,
                    "max_length": 9,
                    "custom_id": "student_id",
                },
                {
                    "label": "School Email",
                    "placeholder": "Enter your .edu email",
                    "required": True,
                    "custom_id": "school_email",
                },
                {
                    "label": "Graduation Year",
                    "placeholder": "Expected graduation year",
                    "required": True,
                    "min_length": 4,
                    "max_length": 4,
                    "custom_id": "graduation_year",
                },
                {
                    "label": "Major(s)",
                    "placeholder": "Enter your Major(s) (separate multiple with commas)",
                    "required": True,
                    "custom_id": "majors",
                },
            ],
        },
    },
    "major_dropdown": {"ephemeral": True, "buttons": (True, True), "dropdowns": []},
    "verify_modal": {
        "ephemeral": True,
        "button_label": "Enter Verification Code",
        "button_style": ButtonStyle.primary,
        "message_prompt": "📧 A verification code has been sent to your email.\nClick below when ready to verify:",
        "modal": {
            "title": "Email Verification",
            "fields": [
                {
                    "label": "Verification Code",
                    "placeholder": "Enter the 6-digit code sent to your email",
                    "required": True,
                    "max_length": 6,
                    "min_length": 6,
                    "custom_id": "verification_code",
                }
            ],
        },
    },
}
