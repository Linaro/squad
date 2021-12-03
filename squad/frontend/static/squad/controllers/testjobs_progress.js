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
                var span_percentage = $('#progress-percentage');
                var span_finished = $('#progress-finished');
                var span_total = $('#progress-total');
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

                    div_complete.css('width', ((progress_complete / total) * 100) + '%');
                    div_failed.css('width', ((progress_failed / total) * 100) + '%');
                    div_running.css('width', ((progress_running / total) * 100) + '%');
                    div_none.css('width', ((progress_none / total) * 100) + '%');

                    div_complete.attr('data-original-title', progress_complete);
                    div_failed.attr('data-original-title', progress_failed);
                    div_running.attr('data-original-title', progress_running);
                    div_none.attr('data-original-title', progress_none);
                } else {
                    var environments = Object.keys(summary);
                    var env_summaries = {};
                    var max_jobs = -1;
                    environments.forEach(function(env) {
                        var env_summary = summary[env];
                        var progress_complete = env_summary.Complete || 0;
                        var progress_failed = (env_summary.Incomplete || 0) + (env_summary.Canceled || 0);
                        var progress_running = env_summary.Running || 0;
                        var progress_none = (env_summary.null || 0) + (env_summary.Submitted || 0);
                        var env_total = progress_complete + progress_failed + progress_running + progress_none;
                        var env_finished = progress_complete + progress_failed;
                        total += env_total;
                        total_finished += env_finished;
                        env_summaries[env] = {
                            'complete': progress_complete,
                            'failed': progress_failed,
                            'running': progress_running,
                            'none': progress_none,
                            'total': env_total,
                            'finished': env_finished
                        };

                        if (env_total > max_jobs) {
                            max_jobs = env_total;
                        }
                    });

                    // Resize bars, calculating shrink factor on the fly
                    environments.forEach(function(env) {
                        var progress_complete = env_summaries[env]['complete'];
                        var progress_failed = env_summaries[env]['failed'];
                        var progress_running = env_summaries[env]['running'];
                        var progress_none = env_summaries[env]['none'];
                        var env_total = env_summaries[env]['total'];
                        var env_finished = env_summaries[env]['finished'];

                        // No jobs for this environment, weird but could happen
                        if (env_total == 0) {
                            return;
                        }

                        var env_key = env.replaceAll('-', '_').replaceAll(' ', '_');
                        var div_complete = $('#progress-complete-' + env_key);
                        var div_failed   = $('#progress-failed-' + env_key);
                        var div_running  = $('#progress-running-' + env_key);
                        var div_none     = $('#progress-none-' + env_key);

                        var span_percentage = $('#progress-percentage-' + env_key);
                        var span_finished   = $('#progress-finished-' + env_key);
                        var span_total      = $('#progress-total-' + env_key);

                        span_percentage.text(Math.trunc((env_finished / env_total) * 100) + '%');
                        span_finished.text(env_finished)
                        span_total.text(env_total)

                        var shrink_factor = env_total / max_jobs;

                        div_complete.css('width', shrink_factor * ((progress_complete / env_total) * 100) + '%');
                        div_failed.css('width', shrink_factor * ((progress_failed / env_total) * 100) + '%');
                        div_running.css('width', shrink_factor * ((progress_running / env_total) * 100) + '%');
                        div_none.css('width', shrink_factor * ((progress_none / env_total) * 100) + '%');

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

                span_percentage.text(Math.trunc((total_finished / total) * 100) + '%');
                span_finished.text(total_finished)
                span_total.text(total)

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
