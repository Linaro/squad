function Config(app, configs) {
    configs.forEach(function(config){
        if(available_configs[config]) {
            available_configs[config](app);
        }
    })
}

var available_configs = {
    'locationProvider': function (app) {
        app.config(['$locationProvider', function($locationProvider) {
            $locationProvider.html5Mode({
                enabled: true,
                requireBase: false
            });
        }]);
    },

    'httpProvider': function (app) {
        app.config(['$httpProvider', function($httpProvider) {
            $httpProvider.defaults.headers.common['X-CSRFToken'] = window.csrf_token;
            $httpProvider.defaults.headers.common['Content-Type'] = 'application/x-www-form-urlencoded';
        }]);
    }
}

export {
    Config
}
