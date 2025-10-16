from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from core.models import User, UserPoint, PointTransaction
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync old point system with new unified point system'

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
        
        # 古いpointsフィールドからUserPointへの移行
        self.sync_user_points(dry_run)
        
        # ランクアップの同期
        self.sync_user_ranks(dry_run)
        
        self.stdout.write(
            self.style.SUCCESS('Point system synchronization completed')
        )

    def sync_user_points(self, dry_run=False):
        """古いpointsフィールドからUserPointシステムへ移行"""
        self.stdout.write('Syncing user points...')
        
        # pointsフィールドを持つユーザーを取得（存在する場合）
        users_with_points = []
        try:
            # pointsフィールドが存在するかチェック
            from django.db import connection
            cursor = connection.cursor()
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='core_user' AND column_name='points'")
            if cursor.fetchone():
                # pointsフィールドが存在する場合のクエリ
                cursor.execute("SELECT id, username, points FROM core_user WHERE points > 0")
                users_with_points = cursor.fetchall()
        except Exception as e:
            self.stdout.write(f'No old points field found or error: {e}')
            return
        
        migrated_count = 0
        for user_data in users_with_points:
            user_id, username, points = user_data
            
            try:
                user = User.objects.get(id=user_id)
                
                # 既存のUserPointがない場合のみ作成
                if not user.user_points.exists():
                    if not dry_run:
                        # 6ヶ月後の有効期限でUserPointを作成
                        expiry_date = timezone.now() + timedelta(days=180)
                        UserPoint.objects.create(
                            user=user,
                            points=points,
                            expiry_date=expiry_date
                        )
                        
                        # 取引履歴も作成
                        PointTransaction.objects.create(
                            user=user,
                            points=points,
                            transaction_type='grant',
                            description=f'システム移行: {points}pt',
                            balance_before=0,
                            balance_after=points
                        )
                    
                    migrated_count += 1
                    self.stdout.write(f'{"[DRY RUN] " if dry_run else ""}Migrated {points}pt for user {username}')
                    
            except User.DoesNotExist:
                self.stdout.write(f'User {username} not found, skipping')
                continue
        
        self.stdout.write(f'{"[DRY RUN] " if dry_run else ""}Migrated points for {migrated_count} users')

    def sync_user_ranks(self, dry_run=False):
        """ユーザーランクの同期"""
        self.stdout.write('Syncing user ranks...')
        
        updated_count = 0
        for user in User.objects.filter(role='customer'):
            old_rank = user.rank
            
            if not dry_run:
                user.check_and_update_rank()
                user.refresh_from_db()
            
            if user.rank != old_rank:
                updated_count += 1
                self.stdout.write(f'{"[DRY RUN] " if dry_run else ""}Updated rank for {user.username}: {old_rank} -> {user.rank}')
        
        self.stdout.write(f'{"[DRY RUN] " if dry_run else ""}Updated ranks for {updated_count} users')

    def cleanup_expired_points(self, dry_run=False):
        """期限切れポイントのクリーンアップ"""
        self.stdout.write('Cleaning up expired points...')
        
        expired_points = UserPoint.objects.filter(
            expiry_date__lt=timezone.now(),
            is_expired=False
        )
        
        expired_count = expired_points.count()
        
        if not dry_run:
            from core.point_service import point_service
            point_service.check_expired_points()
        
        self.stdout.write(f'{"[DRY RUN] " if dry_run else ""}Processed {expired_count} expired point records')