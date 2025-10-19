# 🚨 Early Warning System (EWS) - Complete Guide

## 📋 Overview

The Early Warning System monitors AIS data in real-time and automatically sends email alerts when illegal transhipment activities are detected.

## 🎯 Features

✅ **Real-time Monitoring** - Continuous anomaly detection  
✅ **Email Alerts** - Instant notifications when anomalies detected  
✅ **Priority Levels** - High priority for extended transhipments  
✅ **Alert History** - Track all detected anomalies  
✅ **Duplicate Prevention** - Avoid sending duplicate alerts  
✅ **Simulation Tool** - Test system with realistic scenarios  

---

## 📦 New Components

### 1. **email_config.py**
Handles email configuration and sending alerts

### 2. **simulate_anomaly.py**
Injects test data to trigger anomaly detection

### 3. **early_warning_monitor.py**
Continuous monitoring service that detects and alerts

---

## 🚀 Quick Start

### Step 1: Setup Email Configuration

Edit `backend/.env` and add your email settings:

```bash
# For Gmail (recommended for testing)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
RECIPIENT_EMAILS=recipient1@example.com,recipient2@example.com
CC_EMAILS=supervisor@example.com
```

#### 🔐 Gmail Setup (Recommended)

1. **Enable 2-Factor Authentication**:
   - Go to Google Account → Security
   - Enable 2-Step Verification

2. **Generate App Password**:
   - Go to: https://myaccount.google.com/apppasswords
   - Select "Mail" and "Other (Custom name)"
   - Name it: "AIS Transhipment System"
   - Copy the 16-character password
   - Use this as `SENDER_PASSWORD` (no spaces)

3. **Update .env**:
   ```bash
   SENDER_EMAIL=your_gmail@gmail.com
   SENDER_PASSWORD=abcd efgh ijkl mnop  # 16-char app password
   RECIPIENT_EMAILS=alert_recipient@example.com
   ```

#### 📧 Other Email Providers

**Outlook/Hotmail**:
```bash
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
```

**Yahoo Mail**:
```bash
SMTP_SERVER=smtp.mail.yahoo.com
SMTP_PORT=587
```

**Custom SMTP**:
```bash
SMTP_SERVER=your-smtp-server.com
SMTP_PORT=587
```

### Step 2: Copy New Files

Copy these files to `backend/`:
- `email_config.py`
- `simulate_anomaly.py`
- `early_warning_monitor.py`

```bash
cd ~/ais-transhipment-web/backend
# Copy the three files here
```

### Step 3: Test Email Configuration

```bash
cd backend
source ../venv/bin/activate
python email_config.py
```

**Expected output**:
```
Testing email configuration...
SMTP Server: smtp.gmail.com:587
Sender: your_email@gmail.com
Recipients: ['recipient@example.com']
📧 Sending email alert to 1 recipient(s)...
✅ Email alert sent successfully to: recipient@example.com
```

If successful, check your inbox for the test email! 📬

---

## 🎮 Usage Guide

### Method 1: Simulate Anomaly → Auto Alert

This is the **main workflow** you requested!

#### Step 1: Run Simulator

```bash
cd backend
source ../venv/bin/activate
python simulate_anomaly.py
```

**Interactive Menu**:
```
🎯 ANOMALY SIMULATOR - Choose a scenario:
================================================================

[1] Single Transhipment (30+ min)
    Simulates one vessel pair meeting for 35 minutes
    Duration: 35 min | Pairs: 1

[2] High Priority Alert (45+ min)
    Simulates extended transhipment (50 min) - triggers HIGH PRIORITY alert
    Duration: 50 min | Pairs: 1

[3] Multiple Simultaneous Transhipments
    Simulates 3 vessel pairs conducting transhipment at same time
    Duration: 40 min | Pairs: 3

[4] Borderline Case (30 min exactly)
    Exactly at threshold - tests edge case detection
    Duration: 30 min | Pairs: 1

[5] Quick Test (Fast insertion)
    Same as scenario 1 but inserts data quickly for testing
    Duration: 35 min | Pairs: 1

[Q] Quit
```

#### Step 2: Choose Scenario

```bash
Select scenario (1-5) or Q to quit: 2  # High priority test

Choose insertion mode:
  [F] Fast (instant)
  [R] Real-time (1 sec per minute)
Choice (F/R): F  # Fast mode for quick testing

⚠️  This will insert simulated data into the database. Continue? (y/n): y
```

**Output**:
```
========================================
🚢 ANOMALY SIMULATION: High Priority Alert (45+ min)
========================================
✅ Connected to MongoDB: ais_transhipment_db
📝 Generating 50 minutes of data for 1 vessel pair(s)...
⚡ Fast mode: Inserting all data at once...
✅ Inserted 100 documents instantly
✅ Simulation complete!
```

#### Step 3: Trigger Detection

**Option A: Manual trigger** (immediate):
```bash
python early_warning_monitor.py --check-now
```

**Option B: Start continuous monitoring**:
```bash
python early_warning_monitor.py
```

**Output**:
```
🔍 Checking data from last 60 minutes...
   📊 Found 100 AIS signals from 2 vessels
   🔬 Running anomaly detection...
   ✅ Detection complete: 1 confirmed, 0 candidates

🚨 ALERT: 1 confirmed anomaly(ies) detected!

📧 Sending email alert for 1 new anomaly(ies)...
✅ Email alert sent successfully
   ✅ Email alert sent and recorded

📋 Detected Anomalies:
   • MMSI 100000000 ↔ 200000000: 50.0 min at (-6.1000, 105.6000)
```

#### Step 4: Check Your Email! 📬

You'll receive an email like this:

**Subject**: 🚨 ALERT: 1 Suspected Transhipment(s) Detected - 2025-10-20 15:30 UTC

**Body**:
```
🔴 HIGH PRIORITY
🚢 Illegal Transhipment Detection
Detected at: 2025-10-20 15:30:00 UTC

📊 Detection Summary
Total Anomalies Detected: 1
Priority Level: HIGH - Immediate Action Required

🔍 Detected Anomalies:

Anomaly #1 - 🔴 HIGH PRIORITY
Vessel Pair: MMSI 100000000 ↔ MMSI 200000000
Duration: 50.0 minutes
Start Time: 2025-10-20 14:40:00
End Time: 2025-10-20 15:30:00
Location: -6.1000°, 105.6000°
Google Maps: [View on Map]

⚡ Immediate Actions Required:
• Verify vessel identities and movements
• Check vessel registration and permits
• Coordinate with maritime patrol units
• Document all evidence for investigation
```

---

### Method 2: Continuous Monitoring

For **production** use - runs 24/7 and alerts automatically:

```bash
cd backend
source ../venv/bin/activate

# Start monitoring
python early_warning_monitor.py

# Or run in background
nohup python early_warning_monitor.py > monitor.log 2>&1 &
```

**Output**:
```
================================================================================
🚢 AIS TRANSHIPMENT - EARLY WARNING SYSTEM
================================================================================
Database: ais_transhipment_db
Check Interval: Every 5 minutes
Lookback Window: 60 minutes
Email Alerts: Enabled

Detection Parameters:
  • proximity_km: 0.2
  • duration_min: 30
  • sog_threshold: 0.5
  • port_distance_km: 10.0
================================================================================

⏰ Starting monitoring... (Press Ctrl+C to stop)

================================================================================
🔄 Check #1 - 2025-10-20 15:35:00 UTC
================================================================================
🔍 Checking data from last 60 minutes...
✅ No anomalies detected - All clear

⏳ Next check in 5 minutes...
```

When anomaly is detected:
```
🚨 ALERT: 1 confirmed anomaly(ies) detected!
📧 Sending email alert for 1 new anomaly(ies)...
✅ Email alert sent successfully
```

---

### Method 3: Scheduled Checks (Cron)

For **periodic** checking without continuous monitoring:

```bash
# Add to crontab
crontab -e

# Check every 10 minutes
*/10 * * * * cd /home/user/ais-transhipment-web/backend && /home/user/ais-transhipment-web/venv/bin/python early_warning_monitor.py --check-now >> /var/log/ais_monitor.log 2>&1
```

---

## 📊 View Alert History

```bash
# View last 10 alerts
python early_warning_monitor.py --mode history

# View last 20 alerts
python early_warning_monitor.py --mode history --history-limit 20
```

**Output**:
```
================================================================================
📜 RECENT ALERT HISTORY (Last 10 alerts)
================================================================================

[1] 2025-10-20 15:30:45
    Anomalies: 1
    Email Sent: ✅ Yes
      • MMSI 100000000 ↔ 200000000: 50.0 min

[2] 2025-10-20 14:15:22
    Anomalies: 3
    Email Sent: ✅ Yes
      • MMSI 100000100 ↔ 200000100: 40.0 min
      • MMSI 100000200 ↔ 200000200: 40.0 min
      • MMSI 100000300 ↔ 200000300: 40.0 min
```

---

## 🎯 Test Scenarios Explained

### Scenario 1: Single Transhipment (30+ min)
- **Purpose**: Basic functionality test
- **Duration**: 35 minutes
- **Expected**: ✅ Alert sent (confirmed anomaly)
- **Priority**: Medium

### Scenario 2: High Priority Alert (45+ min)
- **Purpose**: Test high-priority detection
- **Duration**: 50 minutes
- **Expected**: ✅ Alert sent with HIGH PRIORITY flag
- **Priority**: High 🔴

### Scenario 3: Multiple Simultaneous Transhipments
- **Purpose**: Test multi-anomaly handling
- **Duration**: 40 minutes per pair (3 pairs)
- **Expected**: ✅ Single email with 3 anomalies
- **Priority**: Medium

### Scenario 4: Borderline Case
- **Purpose**: Test threshold boundary
- **Duration**: Exactly 30 minutes
- **Expected**: ✅ Alert sent (at threshold)
- **Priority**: Medium

### Scenario 5: Quick Test
- **Purpose**: Fast testing during development
- **Duration**: 35 minutes (instant insertion)
- **Expected**: ✅ Alert sent quickly
- **Priority**: Medium

---

## ⚙️ Configuration

### Alert Thresholds

Edit `.env` to customize:

```bash
# Minimum duration to trigger alert
ALERT_MIN_DURATION=30

# Duration threshold for HIGH PRIORITY
ALERT_HIGH_PRIORITY_DURATION=45

# Maximum distance from port (km)
ALERT_MAX_PORT_DISTANCE=10.0
```

### Monitoring Intervals

```bash
# How often to check for anomalies (minutes)
MONITOR_CHECK_INTERVAL=5

# How far back to look for data (minutes)
MONITOR_LOOKBACK_WINDOW=60

# Enable/disable email sending
MONITOR_SEND_EMAIL=true
```

### Detection Parameters

```bash
MONITOR_PROXIMITY_KM=0.2
MONITOR_DURATION_MIN=30
MONITOR_SOG_THRESHOLD=0.5
MONITOR_PORT_DISTANCE_KM=10.0
```

---

## 🐛 Troubleshooting

### Issue 1: Email Not Sending

**Check configuration**:
```bash
python email_config.py
```

**Common problems**:
1. **Wrong password**: Use App Password, not regular password
2. **2FA not enabled**: Required for Gmail App Passwords
3. **Less secure apps**: Make sure to use App Password
4. **Firewall**: Port 587 might be blocked

**Solution**:
```bash
# Test SMTP connection
python -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
print('Connection successful!')
"
```

### Issue 2: No Anomalies Detected

**Check data exists**:
```bash
mongosh
use ais_transhipment_db
db.ais_signals.find({simulation: true}).count()
```

**Check time range**:
- Simulator inserts data with current timestamp
- Monitor looks back 60 minutes by default
- Make sure data is within lookback window

**Solution**: Run simulator again or adjust `MONITOR_LOOKBACK_WINDOW`

### Issue 3: Duplicate Alerts

The system automatically prevents duplicate alerts for 24 hours.

**Check alert history**:
```bash
python early_warning_monitor.py --mode history
```

**Clear alert history** (if needed):
```bash
mongosh
use ais_transhipment_db
db.anomaly_alerts.deleteMany({})
```

### Issue 4: Monitor Crashes

**Check logs**:
```bash
# If running in background
tail -f monitor.log

# Check MongoDB connection
sudo systemctl status mongod
```

---

## 📈 Production Deployment

### Using systemd (Recommended)

Create service file: `/etc/systemd/system/ais-monitor.service`

```ini
[Unit]
Description=AIS Transhipment Early Warning Monitor
After=mongod.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/home/your_user/ais-