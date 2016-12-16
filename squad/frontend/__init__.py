import os

static = os.path.join(os.path.dirname(__file__), 'static')

links = [
    ('angularjs', 'libjs-angularjs', '/usr/share/javascript/angular.js'),
    ('bootstrap', 'libjs-bootstrap', '/usr/share/javascript/bootstrap'),
    ('font-awesome', 'fonts-font-awesome', '/usr/share/fonts-font-awesome'),
    ('lodash.js', 'libjs-lodash', '/usr/share/javascript/lodash.js'),
]

failed = False
for lib, package, target in links:
    link_path = os.path.join(static, lib)
    if os.path.exists(link_path):
        continue
    if os.path.exists(target):
        os.symlink(target, link_path)
    else:
        print("E: %s does not exist. Try installing %s" % (target, package))
        print("I: You can also manually download %s to %s" % (lib, link_path))

        failed = True

if failed:
    exit(1)
