import smtplib
from email.utils import formatdate
from email.mime.text import MIMEText

class EmailNotify:
    def __init__(self, config):
        self.ACTIVE = config.getboolean("SEND_EMAIL_NOTIFICATION", False)
        if(self.ACTIVE):
            self.SMTP_SERVER = config.get("SMTP_SERVER")
            self.SMTP_PORT = config.getint("SMTP_PORT", 587)
            self.SMTP_USER = config.get("SMTP_USER")
            self.SMTP_PASS = config.get("SMTP_PASS")
            self.TO_EMAIL = config.get("TO_EMAIL")

            if self.SMTP_SERVER.strip() == "" or \
            self.SMTP_USER.strip() == "" or \
            self.SMTP_PASS.strip() == "" or \
            self.TO_EMAIL.strip() == "": 
                print("Email Settings are not set properly.")
                self.ACTIVE = False

    def notify(self, subject, text):
        if not self.ACTIVE: return

        msg = MIMEText(text)

        msg['Subject'] = subject
        msg['From'] = self.SMTP_USER
        msg['To'] = self.TO_EMAIL
        msg["Date"] = formatdate(localtime=True)


        try:    
            smtp = smtplib.SMTP()
            smtp._host = self.SMTP_SERVER
            smtp.connect(self.SMTP_SERVER, self.SMTP_PORT)
            smtp.starttls() 
            smtp.login(self.SMTP_USER, self.SMTP_PASS)
            smtp.sendmail(self.SMTP_USER, self.TO_EMAIL, msg.as_string())
            smtp.quit()

            print("Email sent successfully!")
        except Exception as ex:
            print("Email send failed!")
            print("Something went wrong….",ex)