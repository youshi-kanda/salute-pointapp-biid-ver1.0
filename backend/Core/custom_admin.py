"""
カスタムAdmin設定
Django Adminログイン後に運営管理画面にリダイレクト
"""

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse


class CustomAdminSite(admin.AdminSite):
    """
    カスタムAdmin サイト
    ログイン後にシステム設定画面にリダイレクト
    """
    site_header = 'BIID Point App 運営管理'
    site_title = 'BIID 運営管理'
    index_title = 'システム管理ダッシュボード'
    
    def index(self, request, extra_context=None):
        """
        管理画面のインデックス（ログイン後の最初の画面）
        システム設定画面にリダイレクト
        """
        # ログインユーザーかつスタッフメンバーの場合、システム設定画面へリダイレクト
        if request.user.is_authenticated and request.user.is_staff:
            return redirect('/production-admin/')
        
        # 通常のDjango Admin画面を表示
        return super().index(request, extra_context)


# カスタムAdminサイトのインスタンスを作成
custom_admin_site = CustomAdminSite(name='custom_admin')