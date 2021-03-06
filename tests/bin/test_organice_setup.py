from os import rmdir, stat, unlink
from os.path import exists, join
from pytest import fixture
from shutil import rmtree
from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IXGRP, S_IROTH, S_IXOTH, ST_MODE
from subprocess import call
from ..utils import probe_values_in_tuple, pytest_generate_tests  # noqa


def settings_file_for(project, profile):
    """Returns the relative path to a settings file"""
    return join(project, 'settings', profile + '.py')


class TestOrganiceSetup(object):
    """Tests for the startproject() function. Py.test class, must have no ``__init__`` method!"""
    scenario1 = ['default', dict(project_name='test_project_default', cmd_args=[])]
    scenario2 = ['lighttp', dict(project_name='test_project_lighttp',
                                 cmd_args=['--webserver', 'lighttp'])]
    scenarios = [scenario1, scenario2]

    @fixture(scope="session")
    def setup(self, request, project_name):
        """test setup"""

        @request.addfinalizer
        def teardown():
            """test teardown"""
            try:
                unlink('manage.py')
                rmtree(project_name)
                for suffix in ('media', 'static', 'templates'):
                    rmdir(project_name + '.' + suffix)
                unlink(project_name + '.conf')
            except:
                pass

    def test_01_create_project(self, tmpdir, project_name, cmd_args, setup):
        """
        - does setup command execute and finish?
        - does manage script exist, and is it executable?
        """
        mode0755 = oct(S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP | S_IROTH | S_IXOTH)
        manage_script = 'manage.py'
        tmpdir.chdir()
        exit_code = call(['organice-setup',
                          '--set', 'develop', 'TEST_SETTING_01', "'test value'",
                          '--verbosity=0'] + cmd_args + [project_name])
        assert exit_code == 0
        assert exists(manage_script)
        file_mode = oct(stat(manage_script)[ST_MODE])[-4:]
        assert file_mode == mode0755

    def test_02_split_project(self, project_name, cmd_args):
        """
        - are subdirectories accessible as modules?
        - do profiles exist?
        """
        project_module = join(project_name, '__init__.py')
        project_settings_module = join(project_name, 'settings', '__init__.py')
        assert exists(project_module)
        assert exists(project_settings_module)
        assert exists(settings_file_for(project_name, 'common'))
        assert exists(settings_file_for(project_name, 'develop'))
        assert exists(settings_file_for(project_name, 'staging'))
        assert exists(settings_file_for(project_name, 'production'))
        for profile in (settings_file_for(project_name, 'staging'),
                        settings_file_for(project_name, 'production')):
            content = open(profile).read()
            assert "ALLOWED_HOSTS = [\n" \
                   "    '%(subdomain)s.organice.io',\n" \
                   "    '%(domain)s',\n" \
                   "]\n" % {
                       'subdomain': project_name,
                       'domain': 'www.example.com',
                   } in content
            assert 'DEBUG = ' in content
            assert 'TEMPLATE_DEBUG = ' in content
            assert 'ALLOWED_HOSTS = [\n' in content
            assert 'DATABASES = {\n' in content
            assert 'MEDIA_ROOT = ' in content
            assert 'STATIC_ROOT = ' in content
            assert 'SECRET_KEY = ' in content

    def test_03_configure_database(self, project_name, cmd_args):
        selected = (cmd_args[cmd_args.index('--database') + 1] if '--database' in cmd_args else "")
        db_engine = {
            settings_file_for(project_name, 'develop'): "sqlite3",
            settings_file_for(project_name, 'staging'): selected,
            settings_file_for(project_name, 'production'): selected,
        }
        for profile in (settings_file_for(project_name, 'develop'),
                        settings_file_for(project_name, 'staging'),
                        settings_file_for(project_name, 'production')):
            content = open(profile).read()
            assert ("DATABASES = {\n"
                    "    'default': {\n"
                    "        'ENGINE': 'django.db.backends.%s'," %
                    db_engine[profile]) in content

    def test_04_configure_installed_apps(self, project_name, cmd_args):
        common_settings = open(settings_file_for(project_name, 'common')).read()
        required_apps = [
            'organice',
            'organice_theme',
            'cms',
            'zinnia',
            'emencia.django.newsletter',
            'todo',
            'media_tree',
            'analytical',
            'allauth',
            'allauth.account',
            'allauth.socialaccount',
            'allauth.socialaccount.providers.facebook',
        ]
        assert probe_values_in_tuple(common_settings, 'INSTALLED_APPS', required_apps)

    def test_05_configure_authentication(self, project_name, cmd_args):
        common_settings = open(settings_file_for(project_name, 'common')).read()
        assert 'SERVER_EMAIL = ADMINS[0][1]' in common_settings
        assert "AUTHENTICATION_BACKENDS = (\n" \
               "    'django.contrib.auth.backends.ModelBackend',\n" \
               "    'allauth.account.auth_backends.AuthenticationBackend',\n" \
               ")\n" in common_settings
        assert "ACCOUNT_AUTHENTICATION_METHOD = 'email'\n" in common_settings
        assert "ACCOUNT_EMAIL_REQUIRED = True\n" in common_settings
        assert "ACCOUNT_USERNAME_REQUIRED = False\n" in common_settings
        assert "LOGIN_REDIRECT_URL = '/'\n" in common_settings
        assert "LOGIN_URL = '/login'\n" in common_settings
        assert "LOGOUT_URL = '/logout'\n" in common_settings

        develop_settings = open(settings_file_for(project_name, 'develop')).read()
        assert "EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'" \
               in develop_settings

    def test_06_configure_cms(self, project_name, cmd_args):
        common_settings = open(settings_file_for(project_name, 'common')).read()
        required_middleware = [
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'solid_i18n.middleware.SolidLocaleMiddleware',
            'cms.middleware.page.CurrentPageMiddleware',
            'cms.middleware.user.CurrentUserMiddleware',
            'cms.middleware.toolbar.ToolbarMiddleware',
            'cms.middleware.language.LanguageCookieMiddleware',
        ]
        required_loaders = [
            'apptemplates.Loader',
        ]
        required_ctx = [
            'allauth.account.context_processors.account',
            'allauth.socialaccount.context_processors.socialaccount',
            'cms.context_processors.media',
            'sekizai.context_processors.sekizai',
            'organice.context_processors.expose',
        ]
        required_mediatree = [
            'media_tree.contrib.media_backends.easy_thumbnails.EasyThumbnailsBackend',
        ]
        assert probe_values_in_tuple(common_settings, 'MIDDLEWARE_CLASSES', required_middleware)
        assert probe_values_in_tuple(common_settings, 'TEMPLATE_LOADERS', required_loaders)
        assert probe_values_in_tuple(common_settings, 'TEMPLATE_CONTEXT_PROCESSORS', required_ctx)
        assert probe_values_in_tuple(common_settings, 'MEDIA_TREE_MEDIA_BACKENDS',
                                     required_mediatree)

    def test_07_configure_newsletter(self, project_name, cmd_args):
        common_settings = open(settings_file_for(project_name, 'common')).read()
        assert "NEWSLETTER_DEFAULT_HEADER_SENDER = " in common_settings
        assert "NEWSLETTER_USE_TINYMCE = True" in common_settings
        assert "NEWSLETTER_TEMPLATES = [\n" in common_settings
        assert "TINYMCE_DEFAULT_CONFIG = {\n" in common_settings

    def test_08_configure_blog(self, project_name, cmd_args):
        common_settings = open(settings_file_for(project_name, 'common')).read()
        assert "ZINNIA_ENTRY_BASE_MODEL = 'cmsplugin_zinnia.placeholder.EntryPlaceholder'" \
               in common_settings
        assert "ZINNIA_WYSIWYG = 'wymeditor'" in common_settings
        assert "SOUTH_MIGRATION_MODULES = {" in common_settings

    def test_09_configure_set_custom(self, project_name, cmd_args):
        settings = open(settings_file_for(project_name, 'develop')).read()
        assert "TEST_SETTING_01 = 'test value'" in settings

    def test_10_generate_urls_conf(self, project_name, cmd_args):
        project_urls_file = join(project_name, 'urls.py')
        assert exists(project_urls_file)
        assert open(project_urls_file).read() == '# generated by django Organice\n' \
                                                 'from organice.urls import urlpatterns\n'

    def test_11_generate_webserver_conf(self, project_name, cmd_args):
        webserver = (cmd_args[cmd_args.index('--webserver') + 1]
                     if '--webserver' in cmd_args else 'apache')
        wsgi_conf = join(project_name, 'wsgi.py')
        lighttp_conf = project_name + '.conf'
        conf_values = {
            'project': project_name,
            'domain': 'www.example.com',
        }

        if webserver == 'lighttp':
            assert not exists(wsgi_conf)
            assert exists(lighttp_conf)

            content = open(lighttp_conf).read()
            for line in [
                '$HTTP["host"] =~ "^(%(project)s.organice.io|%(domain)s)$" {\n',
                '                "socket" => env.HOME + "/organice/%(project)s.sock",\n',
                '        "/media/" => env.HOME + "/organice/%(project)s.media/",\n',
                '        "/static/" => env.HOME + "/organice/%(project)s.static/",\n',
                '$HTTP["host"] != "%(domain)s" {\n',
                '    url.redirect = ("^/django.fcgi(.*)$" => "http://%(domain)s$1")\n',
            ]:
                line = (line % conf_values)
                assert line in content

            for profile in (settings_file_for(project_name, 'develop'),
                            settings_file_for(project_name, 'staging'),
                            settings_file_for(project_name, 'production')):
                content = open(profile).read()
                assert 'WSGI_APPLICATION = ' not in content
                assert "FORCE_SCRIPT_NAME = ''" in content

        elif webserver == 'apache':  # default
            assert exists(wsgi_conf)
            for profile in (settings_file_for(project_name, 'develop'),
                            settings_file_for(project_name, 'staging'),
                            settings_file_for(project_name, 'production')):
                content = open(profile).read()
                assert 'WSGI_APPLICATION = ' in content
