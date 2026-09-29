from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, CandidateProfile, EmployerProfile
from .forms import UserRegistrationForm


class EmployerProfileInline(admin.StackedInline):
    model = EmployerProfile
    can_delete = False
    verbose_name_plural = "Employer Profile Data"

class CandidateProfileInline(admin.StackedInline):
    model = CandidateProfile
    can_delete = False
    verbose_name_plural = "Candidate Profile Data"

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    add_form = UserRegistrationForm
    fieldsets = (
        (None, { 'fields' : ('email', 'password') }),
        (_('Personal info'), { 'fields' : ('phone', 'role', 'is_verified') }),
        (_('Permissions'), { 'fields' : ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions') }),
        (_('Important dates'), { 'fields' : ('last_login',) }),
    )

    add_fieldsets = (
        (None, {
            'classes' : ('wide',),
            'fields' : ('email', 'password', "password2", 'role', 'phone',),
        }),
    )

    list_display = ( 'id', 'email', 'role', 'is_verified', 'is_staff', 'created_at' )
    list_filter = ('role', 'is_verified', 'is_staff', 'is_superuser')
    search_fields = ('email', 'phone')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')

    def get_inline_instances(self, request, obj = None):
        if not obj:
            return []

        inlines = []
        if obj.role == User.Role.EMPLOYER:
            inlines.append(EmployerProfileInline(self.model, self.admin_site))
        elif obj.role == User.Role.CANDIDATE:
            inlines.append(CandidateProfileInline(self.model, self.admin_site))
        return inlines


@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):
    list_display = ( 'id','company_name', 'user',)
    search_fields = ('company_name', 'user__email',)
    ordering = ('company_name',)

@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ( 'id','user', 'skills',)
    search_fields = ('user__email',)
   