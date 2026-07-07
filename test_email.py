import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

EMAIL_USER = "sbrinatsya3@gmail.com"
EMAIL_PASSWORD = "Nurish@UTM123"  # Put your app password here
EMAIL_TO = "sbrinatsya3@gmail.com"

subject = "Test Email from SKS Mall System"
body = """
<html>
<body>
<h2>Test Email</h2>
<p>This is a test email from your SKS Mall Lost & Found System.</p>
<p>If you received this, email is working!</p>
</body>
</html>
"""

try:
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))
    
    print("Connecting to Gmail...")
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    print("Logging in...")
    server.login(EMAIL_USER, EMAIL_PASSWORD)
    print("Sending email...")
    server.send_message(msg)
    server.quit()
    print("✅ Email sent successfully!")
    
except Exception as e:
    print(f"❌ Error: {e}")