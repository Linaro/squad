function CompareController($scope, $http, $location) {

    $scope.updateKnownIssue = function() {
        if ($scope.selectedSuite != undefined && $scope.selectedTest != undefined) {
            $http.get('/api/knownissues', {params: {'test_name': $scope.selectedSuite + "/" + $scope.selectedTest, 'active': true}})
                .then(function(response) {
                    if (response.data.count > 0){
                        $scope.hasKnownIssue = true;
                        $scope.knownIssues = response.data.results;
                    } else {
                        $scope.hasKnownIssue = false;
                        $scope.knownIssues = undefined
                    }
               })
        } else {
            $scope.hasKnownIssue = false;
            $scope.knownIssues = undefined;
        }
    }

    $scope.updateURL = function() {
        var search_params = {
            project: $scope.getProjectIds(),
        }
        if ($scope.selectedSuite != undefined) {
            search_params['suite'] = $scope.selectedSuite;
        }
        if ($scope.selectedTest != undefined) {
            search_params['test'] = $scope.selectedTest;
        }
        $location.search(search_params);
        $scope.$evalAsync();
    }

    $scope.getProjectIds = function() {
        return _.map($scope.selectedProjects, function(pr) {return pr.id})
    }

    $scope.addProject = function(project) {
        var existing = _.find($scope.selectedProjects, function(m) {
            return m.id == project.id;
        })
        if (!existing) {
            $scope.selectedProjects.push(project)
            $scope.showProgress[project.id] = true;
        }
        $scope.project = undefined;
        if ($scope.selectedTest && $scope.selectedSuite) {
            $scope.showResults = true;
            $scope.doCompare()
        }
        $scope.updateURL();
    }

    $scope.removeProject = function(project) {
        _.remove($scope.selectedProjects, function(m) {
            return m.id == project.id
        })
        if ($scope.selectedProjects.length == 0) {
            $scope.showResults = false;
            $scope.removeSuite();
            $scope.removeTest();

        } else if ($scope.selectedTest && $scope.selectedSuite) {
            $scope.showResults = true;
            $scope.doCompare()
        }

        $scope.updateURL();
    }

    $scope.addSuite = function(suite) {
        if ($scope.selectedSuite != suite.suite) {
            $scope.removeTest();
        }
        $scope.selectedSuite = suite.suite;
        $scope.suite = undefined;
        if ($scope.selectedTest && $scope.selectedProjects.length > 0) {
            $scope.showResults = true;
            $scope.doCompare()
        }
        $scope.updateURL();
    }

    $scope.removeSuite = function() {
        $scope.selectedSuite = undefined;
        $scope.selectedTest = undefined;
        $(".suite-select").val(null).trigger('change');
        $scope.showResults = false;
        $scope.updateURL();
        $scope.updateKnownIssue();
    }

    $scope.addTest = function(test) {
        $scope.selectedTest = test.name;
        $scope.test = undefined;
        if ($scope.selectedSuite && $scope.selectedProjects.length > 0) {
            $scope.showResults = true;
            $scope.doCompare()
        }
        $scope.updateURL();
    }

    $scope.removeTest = function() {
        $scope.selectedTest = undefined;
        $scope.showResults = false;
        $(".test-select").val(null).trigger('change');
        $scope.updateURL();
        $scope.updateKnownIssue();
    }

    $scope.doCompare = function() {
        // get the list of builds for each project
        for (var i = 0; i < $scope.selectedProjects.length; i++) {
            (function(index){
                $scope.showProgress[$scope.selectedProjects[index].id] = true;
                $http.get($scope.selectedProjects[index].url + "test_results/", {params: {'test_name': $scope.selectedSuite + "/" + $scope.selectedTest, "limit": 10}})
                    .then(function(response){
                        $scope.projectBuilds[$scope.selectedProjects[index].id] = response.data;
                        if (response.data.length > 0) {
                            $scope.projectEnvironments[$scope.selectedProjects[index].id] = response.data[0].environments;
                        } else {
                            $scope.projectEnvironments[$scope.selectedProjects[index].id] = new Array();
                        }
                        $scope.showProgress[$scope.selectedProjects[index].id] = false;
                        $scope.loadedLimits[$scope.selectedProjects[index].id] = 10;
                    });
            })(i);
        }
        $scope.updateKnownIssue();
    }

    $scope.loadMoreData = function(project_id) {
        var loadedLimit = $scope.loadedLimits[project_id];
        $scope.showProgress[project_id] = true;
        (function(id){
            var index = $scope.selectedProjects.findIndex(x => x.id == id);
            $http.get($scope.selectedProjects[index].url  + "test_results/", {params: {'test_name': $scope.selectedSuite + "/" + $scope.selectedTest, "limit": 10, "offset": loadedLimit}})
                .then(function(response) {
                    $scope.projectBuilds[id] = $scope.projectBuilds[id].concat(response.data);
                    $scope.loadedLimits[id] += 10;
                    $scope.showProgress[id] = false;
                });
        })(project_id);
    }

    var params = $location.search();
    var project_list = new Array();
    if (params.project instanceof Array) {
        project_list = params.project;
    } else {
        project_list.push(params.project);
    }
    $scope.selectedProjects = new Array();
    $scope.showProgress = new Array();
    $scope.loadedLimits = new Array();
    $scope.showResults = false;
    $scope.hasKnownIssue = false;
    $scope.projectSearchResponses = 0;

    var ngAjax = function(params, success){
        var url = params.url + '?' + $.param(params.data)
        var request = $http.get(url)
        request.then(success)
        return request
    }

    $(".project-select").select2({
        ajax: {
            transport: ngAjax,
            url: "/api/projects",
            dataType: 'json',
            data: function (params) {
                var term = params.term == undefined ? '' : params.term
                var filters = "%28group__slug__icontains%253D" + term +
                    "%29%20%7C%20%28group__name__icontains%253D" + term +
                    "%29%20%7C%20%28name__icontains%253D" + term +
                    "%29%20%7C%20%28slug__icontains%253D" + term +
                    "%29";
                return {
                    filters: filters, // search term
                    offset: params.page * 50 || 0,
                    page: params.page
                };
            },
            processResults: function (data, params) {
                data = data.data
                params.page = params.page || 0;
                for(var item in data.results){
                    data.results[item].text = data.results[item].full_name;
                }
                return {
                    results: data.results,
                    pagination: {
                        more: ((params.page + 1) * 50) < data.count
                    }
                };
            },
        },
        minimumInputLength: 0,
        dropdownAutoWidth : true
    });

    var projectSelect = $(".project-select");
    projectSelect.on('select2:unselect', function(e){
        $scope.removeProject(e.params.data);
    });
    projectSelect.on('select2:select', function(e){
        $scope.addProject(e.params.data)
    });
    $(".suite-select").select2({
        ajax: {
            transport: ngAjax,
            url: "/api/suitemetadata/",
            dataType: 'json',
            data: function (params) {
                var term = params.term == undefined ? '' : params.term
                return {
                    suite__startswith: term, // search term
                    project: $scope.getProjectIds().join(),
                    kind: 'suite',
                    offset: params.page * 50 || 0,
                    page: params.page
                };
            },
            processResults: function (data, params) {
                data = data.data
                params.page = params.page || 0;
                for(var item in data.results){
                    data.results[item].text = data.results[item].suite;
                }
                return {
                    results: data.results,
                    pagination: {
                        more: ((params.page + 1) * 50) < data.count
                    }
                };
            },
        },
        minimumInputLength: 0,
        dropdownAutoWidth : true
    });
    var suiteSelect = $(".suite-select");
    suiteSelect.on('select2:unselect', function(e){
        $scope.removeSuite(e.params.data);
    });
    suiteSelect.on('select2:select', function(e){
        $scope.addSuite(e.params.data);
    });

    $(".test-select").select2({
        ajax: {
            transport: ngAjax,
            url: "/api/suitemetadata/",
            dataType: 'json',
            data: function (params) {
                var term = params.term == undefined ? '' : params.term
                return {
                    name__startswith: term, // search term
                    project: $scope.getProjectIds().join(),
                    kind: 'test',
                    suite: $scope.selectedSuite,
                    offset: params.page * 50 || 0,
                    page: params.page
                };
            },
            processResults: function (data, params) {
                data = data.data
                params.page = params.page || 0;
                for(var item in data.results){
                    data.results[item].text = data.results[item].name;
                }
                return {
                    results: data.results,
                    pagination: {
                        more: ((params.page + 1) * 50) < data.count
                    }
                };
            },
        },
        minimumInputLength: 0,
        dropdownAutoWidth : true
    });
    var testSelect = $(".test-select");
    testSelect.on('select2:unselect', function(e){
        $scope.removeTest(e.params.data);
    });
    testSelect.on('select2:select', function(e){
        $scope.addTest(e.params.data)
    });

    $scope.selectedSuite = params.suite;
    $scope.selectedTest = params.test;
	$http.get('/api/projects', {params: {'id__in': project_list.join()}})
        .then(function(response) {
            // This will break when there are more than 50 projects
            // However this is an unlikely situation
            $scope.projects = response.data.results;
            $scope.selectedProjects = _.filter($scope.projects, function(project) {
                var found = _.find(_.castArray(params.project), function(param) {
                    if (param == project.id) {
                        return param
                    }
                })
                return found
            })
            for (var i = 0; i < $scope.selectedProjects.length; i++) {
                $scope.showProgress[$scope.selectedProjects[i].id] = true;

                var option = new Option($scope.selectedProjects[i].full_name, $scope.selectedProjects[i].id, true, true);
                option.url = $scope.selectedProjects[i].url;
                projectSelect.append(option).trigger('change');
                projectSelect.trigger({
                    type: 'select2:select',
                    params: {
                        data: $scope.selectedProjects[i]
                    }
                });

            }
            if("undefined" !== typeof($scope.selectedSuite)) {
                $http.get(
                    '/api/suitemetadata/',
                    {params:
                        {suite: $scope.selectedSuite, // search term
                         project: $scope.getProjectIds().join(),
                         kind: 'suite'}
                    }).then(function(response) {
                        var option = new Option($scope.selectedSuite, response.data.results[0].id, true, true);
                        suiteSelect.append(option).trigger('change');
                        suiteSelect.trigger({
                            type: 'select2:select',
                            params: {
                                data: response.data.results[0]
                            }
                        })
                });
            }
            if("undefined" !== typeof($scope.selectedSuite) && "undefined" !== typeof($scope.selectedTest)) {
                $http.get(
                    '/api/suitemetadata/',
                    {params:
                        {suite: $scope.selectedSuite,
                         project: $scope.getProjectIds().join(),
                         name: $scope.selectedTest,
                         kind: 'test'}
                    }).then(function(response) {
                        var option = new Option($scope.selectedTest, response.data.results[0].id, true, true);
                        testSelect.append(option).trigger('change');
                        testSelect.trigger({
                            type: 'select2:select',
                            params: {
                                data: response.data.results[0]
                            }
                        })
                });
            }

            if ($scope.selectedSuite && $scope.selectedTest && $scope.selectedProjects.length > 0) {
                $scope.showResults = true;
                $scope.doCompare();
            }
        }); // end $http.get
    $scope.updateKnownIssue();

    $scope.projectBuilds = new Array();
    $scope.projectEnvironments = new Array();
}

export {
    CompareController
}
