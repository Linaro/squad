module.exports = function(config) {
    config.set({
        // root path location that will be used to resolve all relative paths
        basePath : '../',

        // files to include, ordered by dependencies
        files : [
            'squad/frontend/static/angularjs/angular.js',
            'squad/frontend/static/angularjs/angular-mocks.js',
            'squad/frontend/static/jquery.js',
            'squad/frontend/static/lodash.js',
            'squad/frontend/static/bootstrap/js/bootstrap.js',
            'squad/frontend/static/floatThead/src/jquery.floatThead.js',
            'squad/frontend/static/chartjs/Chart.bundle.js',
            'squad/frontend/static/select2.js/select2.min.js',

            {pattern: 'squad/frontend/static/squad/controllers/*.js', type: 'module'},
            {pattern: 'test/unit/*.js', type: 'module'},
        ],

        autoWatch : false,
        frameworks: ['jasmine'],
        browsers: ['ChromeHeadlessNoSandbox'],
        customLaunchers: {
            ChromeHeadlessNoSandbox: {
                base: 'ChromeHeadless',
                flags: [
                    '--no-sandbox', // required to run without privileges in docker
                    '--user-data-dir=/tmp/chrome-test-profile',
                    '--disable-web-security'
                ]
            }
        },
        reporters: ['progress'],

        plugins : [
            'karma-chrome-launcher',
            'karma-jasmine',
        ]
})}
