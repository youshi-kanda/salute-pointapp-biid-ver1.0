from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import EmailTemplate
from core.email_templates import EMAIL_TEMPLATES


class Command(BaseCommand):
    help = 'Load initial email templates'

    def handle(self, *args, **options):
        with transaction.atomic():
            for template_data in EMAIL_TEMPLATES.values():
                template, created = EmailTemplate.objects.get_or_create(
                    name=template_data['name'],
                    defaults={
                        'subject': template_data['subject'],
                        'body_html': template_data['body_html'],
                        'body_text': template_data['body_text'],
                        'description': template_data['description'],
                        'available_variables': template_data['available_variables'],
                    }
                )
                
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created template: {template.name}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Template already exists: {template.name}')
                    )
        
        self.stdout.write(
            self.style.SUCCESS('Successfully loaded email templates')
        )