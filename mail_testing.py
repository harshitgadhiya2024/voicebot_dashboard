import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os


def send_mail_user(email_sender, email_password, to_m, server, port, file_paths):
    try:
        # Create the email
        message = MIMEMultipart()
        message['From'] = email_sender
        message['To'] = email_receiver
        message['Subject'] = 'Subject of the Email'

        # Add body to the email
        body = 'This is the body of the email'
        message.attach(MIMEText(body, 'plain'))

        # Attach each file in the list
        for file_path in file_paths:
            try:
                with open(file_path, 'rb') as attachment:
                    # Create a MIMEBase object
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())

                # Encode the payload using base64 encoding
                encoders.encode_base64(part)
                filename = file_path.split("\\")[-1]
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {filename}',
                )

                # Attach the file to the email
                message.attach(part)
            except Exception as e:
                print(f'Failed to attach {file_path}: {e}')

        # Connect to the SMTP server and send the email
        try:
            print("connect smtp")
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()  # Secure the connection
                server.login(email_sender, email_password)  # Log in to the server
                print("connected")
                server.sendmail(email_sender, email_receiver, message.as_string())  # Send the email
            print('Email sent successfully!')
        except Exception as e:
            print(f'Failed to send email: {e}')

    except Exception as e:
        print(e)

# Email credentials
email_sender = 'codescatter8980@gmail.com'
email_password = 'uwyuodnrwjlmtmzm'
email_receiver = 'harshitgadhiya8980@gmail.com'

# Set up the SMTP server
smtp_server = 'smtp.gmail.com'
smtp_port = 587

# List of files to attach
file_paths = [
    os.path.abspath('output1.wav'),
    os.path.abspath('output2.wav'),
    os.path.abspath('output3.wav')
]

send_mail_user(email_sender, email_password, email_receiver, smtp_server, smtp_port, file_paths)


