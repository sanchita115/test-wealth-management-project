import os
from typing import Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


def get_client() -> Optional[WebClient]:
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token or token.startswith("xoxb-your"):
        return None
    return WebClient(token=token)


def _emoji_for_anomaly(anomaly_type: str) -> str:
    return {
        "spending_spike": ":rotating_light:",
        "category_dominance": ":pie_chart:",
        "large_single_transaction": ":money_with_wings:",
        "week_over_week": ":chart_with_upwards_trend:",
    }.get(anomaly_type, ":bell:")


def send_anomaly_alerts(anomalies: list, stats: dict, channel: Optional[str] = None) -> list:
    client = get_client()
    if not client:
        return ["Slack not configured — set SLACK_BOT_TOKEN and SLACK_CHANNEL_ID in .env"]

    channel = channel or os.getenv("SLACK_CHANNEL_ID", "")
    if not channel:
        return ["No Slack channel configured — set SLACK_CHANNEL_ID in .env"]

    results = []

    summary_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f":bank: *Spending Analysis Complete*\n"
                f"Total spent: *₹{stats['total_expenses']:,.0f}* over {stats['date_range_days']} days\n"
                f"Monthly avg: *₹{stats['avg_monthly_spend']:,.0f}* | "
                f"Net: *{'▲' if stats['net'] >= 0 else '▼'} ₹{abs(stats['net']):,.0f}*"
            ),
        },
    }

    try:
        client.chat_postMessage(
            channel=channel,
            blocks=[summary_block],
            text=f"Spending Analysis: ₹{stats['total_expenses']:,.0f} total over {stats['date_range_days']} days",
        )
        results.append("Summary posted to Slack")
    except SlackApiError as e:
        results.append(f"Failed to post summary: {e.response['error']}")

    for anomaly in anomalies[:5]:
        emoji = _emoji_for_anomaly(anomaly["type"])
        try:
            client.chat_postMessage(
                channel=channel,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{emoji} *Spending Alert*\n{anomaly['message']}",
                        },
                    }
                ],
                text=anomaly["message"],
            )
            results.append(f"Alert sent: {anomaly['type']}")
        except SlackApiError as e:
            results.append(f"Failed to send alert '{anomaly['type']}': {e.response['error']}")

    return results
