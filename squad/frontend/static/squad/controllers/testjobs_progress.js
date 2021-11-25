export function TestJobsProgressController($scope, $http) {
    $scope.build_id = undefined;
    $scope.init = function(build_id, is_build_finished) {
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
        var oneMinute = 60000;

        setTimeout(function updateProgress() {
            $http.get('/api/builds/'+ $scope.build_id +'/testjobs_summary/').then(function(response) {
                var summary = response.data.results;
                console.log(summary);
                var progress_complete = summary.Complete || 0;
                var progress_failed = (summary.Incomplete || 0) + (summary.Canceled || 0);
                var progress_running = summary.Running || 0;
                var progress_none = (summary.null || 0) + (summary.Submitted || 0);
                var total = progress_complete + progress_failed + progress_running + progress_none;

                if (total == 0) {
                    console.log('Detected zero test jobs. Aborting...');
                    return;
                }

                var div_complete = $('#progress-complete');
                var div_failed   = $('#progress-failed');
                var div_running  = $('#progress-running');
                var div_none     = $('#progress-none');
                var div_percentage= $('#progress-percentage');

                div_complete.css('width', Math.trunc((progress_complete / total) * 100) + '%');
                div_failed.css('width', Math.trunc((progress_failed / total) * 100) + '%');
                div_running.css('width', Math.trunc((progress_running / total) * 100) + '%');
                div_none.css('width', Math.trunc((progress_none / total) * 100) + '%');

                div_complete.attr('data-original-title', progress_complete);
                div_failed.attr('data-original-title', progress_failed);
                div_running.attr('data-original-title', progress_running);
                div_none.attr('data-original-title', progress_none);

                div_percentage.text(Math.trunc(((progress_complete + progress_failed) / total) * 100) + '%');

                var finished = (progress_complete + progress_failed) == total;
                if (!finished) {
                    setTimeout(updateProgress, oneMinute);
                    return;
                }
                console.log('testjobs completed');
            }).catch(function (data) {});
        }, oneMinute);
    }
}
