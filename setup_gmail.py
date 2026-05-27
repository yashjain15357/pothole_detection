#!/usr/bin/env python3
"""
SMTP Setup Script for Pothole Detection System
This script creates smtp_config.json for SMTP email sending.

For Gmail:
- Turn on 2-Step Verification
- Create an App Password
- Use your Gmail address as SMTP_EMAIL
- Use the App Password as SMTP_APP_PASSWORD
"""

import json
import smtplib
import ssl
from pathlib import Path

CONFIG_FILE = Path('smtp_config.json')


def prompt_value(label, default=''):
    if default:
        value = input(f'{label} [{default}]: ').strip()
        return value or default
    return input(f'{label}: ').strip()


def setup_smtp():
    print('=' * 60)
    print('SMTP Setup - Pothole Detection System')
    print('=' * 60)
    print()
    print('For Gmail SMTP, use smtp.gmail.com with port 587 and an App Password.')
    print()

    smtp_server = prompt_value('SMTP server', 'smtp.gmail.com')
    smtp_port = prompt_value('SMTP port', '587')
    smtp_email = prompt_value('SMTP email address', 'yourname@gmail.com')
    smtp_app_password = prompt_value('SMTP app password', 'xxxx xxxx xxxx xxxx')
    use_starttls = prompt_value('Use STARTTLS (true/false)', 'true').lower() in ('true', '1', 'yes', 'y')

    if not smtp_email or not smtp_app_password:
        print()
        print('ERROR: SMTP email and app password are required.')
        return False

    config = {
        'SMTP_SERVER': smtp_server,
        'SMTP_PORT': int(smtp_port),
        'SMTP_EMAIL': smtp_email,
        'SMTP_APP_PASSWORD': smtp_app_password,
        'SMTP_USE_STARTTLS': use_starttls,
    }

    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as file:
            json.dump(config, file, indent=2)

        print()
        print(f'✓ SMTP configuration saved to {CONFIG_FILE}')
        print()

        test_now = prompt_value('Test SMTP login now? (true/false)', 'false').lower() in ('true', '1', 'yes', 'y')
        if test_now:
            context = ssl.create_default_context()
            with smtplib.SMTP(config['SMTP_SERVER'], config['SMTP_PORT'], timeout=30) as server:
                if use_starttls:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                server.login(config['SMTP_EMAIL'], config['SMTP_APP_PASSWORD'])
            print('✓ SMTP login test successful')

        print()
        print('Now run: python app.py')
        return True
    except Exception as e:
        print()
        print(f'❌ SMTP setup failed: {e}')
        return False


def main():
    success = setup_smtp()
    raise SystemExit(0 if success else 1)


if __name__ == '__main__':
    main()
