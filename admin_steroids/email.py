import os
import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail.backends.smtp import EmailBackend

class DevelopmentEmailBackend(EmailBackend):
    """
    Redirects all email to an specific domain address
    and appends the hostname to the message.
    
    Designed to be used in development environments, where
    we want to test sending real email, but don't want to risk
    emailing real users.
    """

    def _send(self, email_message):
        """
        A helper method that does the actual sending.
        """
        if not email_message.recipients():
            return False
        try:
            # Set recipient redirect.
            allow_any_on_domain = getattr(
                settings, 'DEV_EMAIL_ALLOW_ANY_ON_DOMAIN', False)
            default_redirect_to = getattr(
                settings,
                'DEV_EMAIL_REDIRECT_TO',
                settings.DEV_EMAIL_REDIRECT_TO)
            default_domain = default_redirect_to.split('@')[1].strip()
            recipients = []
            if allow_any_on_domain:
                for recip in email_message.recipients():
                    try:
                        domain = recip.split('@')[1].strip()
                        if domain == default_domain:
                            recipients.append(recip)
                    except Exception, e:
                        LOG.error("Invalid email recipient: %s" % e)
                        pass
            if not recipients:
                 recipients = [default_redirect_to]
                
            # Append hostname
            message = email_message.message().as_string()
            if getattr(settings, 'DEV_EMAIL_APPEND_HOSTNAME', False):
                message += '\n(Sent from %s)' % settings.BASE_URL
                
            self.connection.sendmail(email_message.from_email,
                    recipients,
                    message)
        except:
            if not self.fail_silently:
                raise
            return False
        return True
        