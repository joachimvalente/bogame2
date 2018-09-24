from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib


def send_email(smtp_host, smtp_port, login, password, addr_to, subject, body):
  msg = MIMEMultipart()
  msg['To'] = addr_to
  msg['Subject'] = subject
  msg.attach(MIMEText(body, 'plain'))

  smtp = smtplib.SMTP(smtp_host, smtp_port)
  smtp.starttls()
  smtp.login(login, password)
  smtp.sendmail(login, addr_to, msg.as_string())
  smtp.quit()
