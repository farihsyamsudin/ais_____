"""
Email Configuration and Notification Service
Handles sending email alerts for detected anomalies
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime
import os
from dotenv import load_dotenv
import folium
import io

load_dotenv()

# Email Configuration
EMAIL_CONFIG = {
    'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
    'smtp_port': int(os.getenv('SMTP_PORT', '587')),
    'sender_email': os.getenv('SENDER_EMAIL', ''),
    'sender_password': os.getenv('SENDER_PASSWORD', ''),
    'recipient_emails': os.getenv('RECIPIENT_EMAILS', '').split(','),
    'cc_emails': os.getenv('CC_EMAILS', '').split(',') if os.getenv('CC_EMAILS') else []
}

# Alert Thresholds
ALERT_CONFIG = {
    'min_duration_for_alert': int(os.getenv('ALERT_MIN_DURATION', '30')),  # minutes
    'high_priority_duration': int(os.getenv('ALERT_HIGH_PRIORITY_DURATION', '45')),  # minutes
    'max_distance_from_port': float(os.getenv('ALERT_MAX_PORT_DISTANCE', '10.0')),  # km
}


def create_email_body(anomalies, detection_time):
    """
    Creates HTML email body with anomaly details
    
    Args:
        anomalies: List of detected anomalies
        detection_time: Timestamp of detection
    
    Returns:
        HTML string
    """
    
    # Determine priority level
    high_priority = any(a['duration_min'] >= ALERT_CONFIG['high_priority_duration'] for a in anomalies)
    priority_label = "🔴 HIGH PRIORITY" if high_priority else "⚠️ ALERT"
    
    html = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .header {{
                background-color: {'#dc2626' if high_priority else '#f59e0b'};
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                padding: 20px;
                background-color: #f9fafb;
            }}
            .anomaly-card {{
                background-color: white;
                border-left: 4px solid {'#dc2626' if high_priority else '#f59e0b'};
                padding: 15px;
                margin: 10px 0;
                border-radius: 4px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .label {{
                font-weight: bold;
                color: #1f2937;
            }}
            .value {{
                color: #4b5563;
            }}
            .footer {{
                padding: 20px;
                text-align: center;
                font-size: 12px;
                color: #6b7280;
                background-color: #f3f4f6;
                border-radius: 0 0 5px 5px;
            }}
            .summary {{
                background-color: #dbeafe;
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 20px;
            }}
            .coordinates {{
                font-family: monospace;
                background-color: #f3f4f6;
                padding: 2px 6px;
                border-radius: 3px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{priority_label}</h1>
            <h2>🚢 Illegal Transhipment Detection</h2>
            <p>Detected at: {detection_time.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
        
        <div class="content">
            <div class="summary">
                <h3>📊 Detection Summary</h3>
                <p><span class="label">Total Anomalies Detected:</span> <span class="value">{len(anomalies)}</span></p>
                <p><span class="label">Detection Time:</span> <span class="value">{detection_time.strftime('%Y-%m-%d %H:%M:%S')}</span></p>
                <p><span class="label">Priority Level:</span> <span class="value">{'HIGH - Immediate Action Required' if high_priority else 'Medium - Review Recommended'}</span></p>
            </div>
            
            <h3>🔍 Detected Anomalies:</h3>
    """
    
    for idx, anomaly in enumerate(anomalies, 1):
        duration = anomaly['duration_min']
        is_high_priority = duration >= ALERT_CONFIG['high_priority_duration']
        
        html += f"""
            <div class="anomaly-card">
                <h4>Anomaly #{idx} {' - 🔴 HIGH PRIORITY' if is_high_priority else ''}</h4>
                <p><span class="label">Vessel Pair:</span> <span class="value">MMSI {anomaly['mmsi_1']} ↔ MMSI {anomaly['mmsi_2']}</span></p>
                <p><span class="label">Duration:</span> <span class="value">{duration:.1f} minutes</span></p>
                <p><span class="label">Start Time:</span> <span class="value">{anomaly['start_time']}</span></p>
                <p><span class="label">End Time:</span> <span class="value">{anomaly['end_time']}</span></p>
                <p><span class="label">Location:</span> <span class="coordinates">{anomaly['lat']:.4f}°, {anomaly['lon']:.4f}°</span></p>
                <p><span class="label">Google Maps:</span> <a href="https://www.google.com/maps?q={anomaly['lat']},{anomaly['lon']}" target="_blank">View on Map</a></p>
            </div>
        """
    
    html += """
            <div style="margin-top: 20px; padding: 15px; background-color: #fef3c7; border-radius: 4px;">
                <p><strong>⚡ Immediate Actions Required:</strong></p>
                <ul>
                    <li>Verify vessel identities and movements</li>
                    <li>Check vessel registration and permits</li>
                    <li>Coordinate with maritime patrol units</li>
                    <li>Document all evidence for investigation</li>
                </ul>
            </div>
        </div>
        
        <div class="footer">
            <p>This is an automated alert from the AIS Transhipment Detection System</p>
            <p>For questions or issues, contact the system administrator</p>
            <p style="font-size: 10px; margin-top: 10px;">
                Detection Parameters: Proximity &lt; 0.2km | Duration &gt; 30min | SOG &lt; 0.5 knots | Distance from ports &gt; 10km
            </p>
        </div>
    </body>
    </html>
    """
    
    return html


def send_email_alert(anomalies, detection_time=None):
    """
    Sends email alert for detected anomalies
    
    Args:
        anomalies: List of anomaly dictionaries
        detection_time: Datetime of detection (defaults to now)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    
    if not anomalies:
        print("No anomalies to report")
        return False
    
    if not EMAIL_CONFIG['sender_email'] or not EMAIL_CONFIG['sender_password']:
        print("❌ Email configuration missing. Please set SENDER_EMAIL and SENDER_PASSWORD in .env")
        return False
    
    if not EMAIL_CONFIG['recipient_emails'] or EMAIL_CONFIG['recipient_emails'] == ['']:
        print("❌ No recipient emails configured. Please set RECIPIENT_EMAILS in .env")
        return False
    
    detection_time = detection_time or datetime.utcnow()
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🚨 ALERT: {len(anomalies)} Suspected Transhipment(s) Detected - {detection_time.strftime('%Y-%m-%d %H:%M UTC')}"
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = ', '.join(EMAIL_CONFIG['recipient_emails'])
        
        if EMAIL_CONFIG['cc_emails'] and EMAIL_CONFIG['cc_emails'] != ['']:
            msg['Cc'] = ', '.join(EMAIL_CONFIG['cc_emails'])
        
        # Create HTML body
        html_body = create_email_body(anomalies, detection_time)
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email
        print(f"📧 Sending email alert to {len(EMAIL_CONFIG['recipient_emails'])} recipient(s)...")
        
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
            
            all_recipients = EMAIL_CONFIG['recipient_emails']
            if EMAIL_CONFIG['cc_emails'] and EMAIL_CONFIG['cc_emails'] != ['']:
                all_recipients += EMAIL_CONFIG['cc_emails']
            
            server.send_message(msg)
        
        print(f"✅ Email alert sent successfully to: {', '.join(EMAIL_CONFIG['recipient_emails'])}")
        return True
    
    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")
        return False


def test_email_configuration():
    """
    Tests email configuration by sending a test email
    
    Returns:
        bool: True if test email sent successfully
    """
    
    test_anomaly = [{
        'mmsi_1': 123456789,
        'mmsi_2': 987654321,
        'duration_min': 45.5,
        'start_time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'end_time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'lat': -6.0,
        'lon': 105.5
    }]
    
    print("Testing email configuration...")
    print(f"SMTP Server: {EMAIL_CONFIG['smtp_server']}:{EMAIL_CONFIG['smtp_port']}")
    print(f"Sender: {EMAIL_CONFIG['sender_email']}")
    print(f"Recipients: {EMAIL_CONFIG['recipient_emails']}")
    
    return send_email_alert(test_anomaly, datetime.utcnow())


if __name__ == "__main__":
    # Run test when executed directly
    test_email_configuration()