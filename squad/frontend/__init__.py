import os

static = os.path.join(os.path.dirname(__file__), 'static')

links = {
    'angularjs': '/usr/share/javascript/angular.js',
    'bootstrap': '/usr/share/javascript/bootstrap',
    'font-awesome': '/usr/share/fonts-font-awesome',
}

for link, target in links.items():
    link_path = os.path.join(static, link)
    if not os.path.exists(link_path):
        os.symlink(target, link_path)
