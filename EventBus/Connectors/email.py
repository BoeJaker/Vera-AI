import smtplib
from email.message import EmailMessage
from Vera.EventBus.Connectors.base import Connector

class EmailConnector(Connector):
    def __init__(self, sender=None, recipient=None, smtp=None, password=None):
        self.sender = sender
        self.recipient = recipient
        self.smtp = smtp
        self.password = password

    async def handle(self, event):
        if not self.smtp:
            return
        msg = EmailMessage()
        msg.set_content(str(event.payload))
        msg["Subject"] = event.type
        msg["From"] = self.sender
        msg["To"] = self.recipient

        with smtplib.SMTP_SSL(self.smtp, 465) as server:
            server.login(self.sender, self.password)
            server.send_message(msg)
