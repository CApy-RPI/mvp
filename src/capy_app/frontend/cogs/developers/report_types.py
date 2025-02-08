from dataclasses import dataclass


@dataclass
class ReportType:
    command: str
    description: str
    modal_title: str
    modal_prompt: str
    channel_id_setting: str
    emoji: str
    embed_title_prefix: str
    embed_color: str
    success_message: str


BUG_REPORT = ReportType(
    command="bug",
    description="Report a bug in the bot",
    modal_title="Bug Report",
    modal_prompt="Please describe the bug in detail...",
    channel_id_setting="BUG_REPORTS_CHANNEL_ID",
    emoji="🐛",
    embed_title_prefix="Bug Report",
    embed_color="RED",
    success_message="Bug report submitted successfully!",
)

FEATURE_REQUEST = ReportType(
    command="feature",
    description="Request a new feature",
    modal_title="Feature Request",
    modal_prompt="Please describe the feature you'd like to see...",
    channel_id_setting="FEATURE_REQUESTS_CHANNEL_ID",
    emoji="💡",
    embed_title_prefix="Feature Request",
    embed_color="GREEN",
    success_message="Feature request submitted successfully!",
)

FEEDBACK = ReportType(
    command="feedback",
    description="Provide general feedback",
    modal_title="Feedback",
    modal_prompt="Please provide your feedback...",
    channel_id_setting="FEEDBACK_CHANNEL_ID",
    emoji="📝",
    embed_title_prefix="Feedback",
    embed_color="BLUE",
    success_message="Feedback submitted successfully!",
)
