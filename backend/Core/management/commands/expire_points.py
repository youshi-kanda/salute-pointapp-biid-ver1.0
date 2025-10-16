from django.core.management.base import BaseCommand
from django.utils import timezone
from core.point_service import point_service
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check and expire outdated points (run daily via cron)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        try:
            if not dry_run:
                expired_count = point_service.check_expired_points()
            else:
                # DRY RUN: 期限切れ予定のポイントを表示
                from core.models import UserPoint
                expired_points = UserPoint.objects.filter(
                    expiry_date__lt=timezone.now(),
                    is_expired=False
                )
                expired_count = expired_points.count()
                
                self.stdout.write(f'Would expire {expired_count} point records:')
                for point in expired_points[:10]:  # 最大10件表示
                    self.stdout.write(f'  - {point.user.username}: {point.points}pt (expired: {point.expiry_date})')
                
                if expired_count > 10:
                    self.stdout.write(f'  ... and {expired_count - 10} more')
            
            self.stdout.write(
                self.style.SUCCESS(f'{"[DRY RUN] " if dry_run else ""}Processed {expired_count} expired point records')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error processing expired points: {str(e)}')
            )
            logger.error(f"Expired points check failed: {str(e)}")
            raise