export function TestJobsProgressController($scope, $http) {
    $scope.build_id = undefined;
    $scope.per_environment = false;
    $scope.init = function(build_id, is_build_finished, per_environment) {
        if (is_build_finished) {
            return;
        }

        // IE doesn't support Math.trunc :/: https://stackoverflow.com/questions/60402658/ie-browser-not-supporting-math-trunc
        if (!Math.trunc) {
            Math.trunc = function (v) {
                return v < 0 ? Math.ceil(v) : Math.floor(v);
            };
        }

        $scope.build_id = build_id;
        $scope.per_environment = per_environment;
        var oneMinute = 60000;
        var summary_url = '/api/builds/'+ $scope.build_id +'/testjobs_summary/';
        if (per_environment) {
            summary_url += '?per_environment=true';
        }

        setTimeout(function updateProgress() {
            $http.get(summary_url).then(function(response) {
                var summary = response.data.results;
                var finished = false;
                var div_percentage= $('#progress-percentage');
                var total_finished = 0;
                var total = 0;

                if (!$scope.per_environment) {
                    var progress_complete = summary.Complete || 0;
                    var progress_failed = (summary.Incomplete || 0) + (summary.Canceled || 0);
                    var progress_running = summary.Running || 0;
                    var progress_none = (summary.null || 0) + (summary.Submitted || 0);
                    total = progress_complete + progress_failed + progress_running + progress_none;
                    total_finished = progress_complete + progress_failed;

                    if (total == 0) {
                        console.log('Detected zero test jobs. Aborting...');
                        return;
                    }

                    var div_complete = $('#progress-complete');
                    var div_failed   = $('#progress-failed');
                    var div_running  = $('#progress-running');
                    var div_none     = $('#progress-none');

                    div_complete.css('width', Math.trunc((progress_complete / total) * 100) + '%');
                    div_failed.css('width', Math.trunc((progress_failed / total) * 100) + '%');
                    div_running.css('width', Math.trunc((progress_running / total) * 100) + '%');
                    div_none.css('width', Math.trunc((progress_none / total) * 100) + '%');

                    div_complete.attr('data-original-title', progress_complete);
                    div_failed.attr('data-original-title', progress_failed);
                    div_running.attr('data-original-title', progress_running);
                    div_none.attr('data-original-title', progress_none);
                } else {
                    var environments = Object.keys(summary);
                    environments.forEach(function(env) {
                        var env_summary = summary[env];
                        var progress_complete = env_summary.Complete || 0;
                        var progress_failed = (env_summary.Incomplete || 0) + (env_summary.Canceled || 0);
                        var progress_running = env_summary.Running || 0;
                        var progress_none = (env_summary.null || 0) + (env_summary.Submitted || 0);
                        var env_total = progress_complete + progress_failed + progress_running + progress_none;
                        total += env_total;
                        total_finished += progress_complete + progress_failed;

                        // No jobs for this environment, weird but could happen
                        if (env_total == 0) {
                            return;
                        }

                        var env_key = env.replaceAll('-', '_').replaceAll(' ', '_');
                        var div_complete = $('#progress-complete-' + env_key);
                        var div_failed   = $('#progress-failed-' + env_key);
                        var div_running  = $('#progress-running-' + env_key);
                        var div_none     = $('#progress-none-' + env_key);

                        div_complete.css('width', Math.trunc((progress_complete / env_total) * 100) + '%');
                        div_failed.css('width', Math.trunc((progress_failed / env_total) * 100) + '%');
                        div_running.css('width', Math.trunc((progress_running / env_total) * 100) + '%');
                        div_none.css('width', Math.trunc((progress_none / env_total) * 100) + '%');

                        div_complete.attr('data-original-title', progress_complete);
                        div_failed.attr('data-original-title', progress_failed);
                        div_running.attr('data-original-title', progress_running);
                        div_none.attr('data-original-title', progress_none);
                    });
                }

                if (total == 0) {
                    console.log('Detected zero test jobs. Aborting...');
                    return;
                }

                div_percentage.text(Math.trunc((total_finished / total) * 100) + '%');

                finished = (total_finished == total);

                if (!finished) {
                    setTimeout(updateProgress, oneMinute);
                    return;
                }
                console.log('testjobs completed');
            }).catch(function (data) {});
        }, oneMinute);
    }
}
