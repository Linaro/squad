var squad_data = {}
var squad_server = "https://qa-reports.linaro.org"

function getAuthType() {
    return { type: 'NONE' };
}

function isAdminUser() {
    return true;
}

function fetchSquadDataFromConfig(request) {

    // Add headers for token authentication.
    var request_options = {}
    if (typeof(request.configParams.token) !== 'undefined') {
        request_options = {
            'headers': {
                'Authorization': 'Token ' + request.configParams.token
            }
        }
    }

    var group_url = [
        squad_server,
        '/api/groups/',
        '?slug=',
        request.configParams.group
    ];
    var group_response = UrlFetchApp.fetch(group_url.join(''),
                                           request_options);
    var group_data = JSON.parse(group_response);
    if (group_data.count == 0) {
        throw new Error("DS_USER:Invalid group slug.");
    }
    squad_data.group = group_data.results[0];

    var project_url = [
        squad_server,
        '/api/projects/',
        '?slug=',
        request.configParams.project,
        '&group=',
        squad_data.group.id
    ];
    var project_response = UrlFetchApp.fetch(project_url.join(''),
                                             request_options);
    var project_data = JSON.parse(project_response);
    if (project_data.count == 0) {
        throw new Error("DS_USER:Invalid project slug.");
    }
    squad_data.project = project_data.results[0];

    var environments_url = [
        squad_server,
        '/api/environments/',
        '?project=',
        squad_data.project.id
    ];
    var environments_response = UrlFetchApp.fetch(environments_url.join(''),
                                                  request_options);
    squad_data.environments = JSON.parse(environments_response).results;
}

function getConfig(request) {

    var cc = DataStudioApp.createCommunityConnector();
    var config = cc.getConfig();

    config.newInfo()
        .setId('instructions')
        .setText('Enter SQUAD user token.');

    config.newTextInput()
        .setId('token')
        .setName('Provide a token for authentication')
        .setHelpText('token')
        .setPlaceholder('token string')
        .setAllowOverride(false);

    config.newInfo()
        .setId('group-info')
        .setText('Provide a SQUAD group.');

    config.newTextInput()
        .setId('group')
        .setName('Provide a group slug')
        .setHelpText('Group slug')
        .setPlaceholder('i.e. lkft')
        .setAllowOverride(false);

    config.newInfo()
        .setId('project-info')
        .setText('Select a SQUAD project for display.');

    config.newTextInput()
        .setId('project')
        .setName('Provide a project slug')
        .setHelpText('Project slug')
        .setPlaceholder('i.e. linux-stable-rc-4.9-oe')
        .setAllowOverride(false);
    config.setDateRangeRequired(false);

    return config.build();
}

function getFields(environments) {
    var cc = DataStudioApp.createCommunityConnector();
    var fields = cc.getFields();
    var types = cc.FieldType;
    var aggregations = cc.AggregationType;

    fields.newDimension()
        .setId('day')
        .setName('Date')
        .setType(types.YEAR_MONTH_DAY);

    fields.newDimension()
        .setId('metric')
        .setName('Metric')
        .setType(types.TEXT);

    for (i in environments) {
        // Only alphanumeric characters allowed in ID.
        fields.newMetric()
            .setId(environments[i].slug.replace(/-/g, '').replace(/_/g, ''))
            .setName(environments[i].slug)
            .setType(types.NUMBER)
            .setAggregation(aggregations.MIN);
    }

    fields.setDefaultDimension('day');

    return fields;
}

function getSchema(request) {
    fetchSquadDataFromConfig(request);
    var fields = getFields(squad_data.environments).build();
    return { 'schema': fields };
}

// Update the element in data list if it already contains the object with
// specific date and metric(if applicable), otherwise adds a new one.
function addElementByDate(data, metric, elem, fieldIndex, dayIndex, fieldIds) {

    var metricIndex = fieldIds.indexOf('metric');
    for (i in data) {
        if (dayIndex != -1) {
            // Match datetime.
            if (data[i][dayIndex] == elem[0]) {
                // Match metric or ignore if there's no metric in requested
                // fields.
                if (metricIndex == -1 || data[i][metricIndex] == metric) {
                    data[i][fieldIndex] = elem[1];
                    return;
                }
            }
        }
    }
    var newElem = Array.apply(null, Array(fieldIds.length)).map(Number.prototype.valueOf, 0);

    if (dayIndex != -1) {
        newElem[dayIndex] = elem[0];
    }
    if (metricIndex != -1) {
        newElem[metricIndex] = metric;
    }
    newElem[fieldIndex] = elem[1];
    data.push(newElem);
}

function getFieldNamesFromSchema(schema) {
    var fieldNames = schema.map(function(field) {
        return field.name;
    });
    return fieldNames;
}

function getData(request) {
    // Init data schema.
    fetchSquadDataFromConfig(request);

    var requestedFieldIds = request.fields.map(function(field) {
        return field.name;
    });
    var dayIndex = requestedFieldIds.indexOf('day');

    var requestedFields = getFields(squad_data.environments).forIds(
        requestedFieldIds);

    // Recreate field IDs array because of the order.
    requestedFieldIds = requestedFields.asArray().map(function(field) {
        return field.getId();
    });

    var environments_params = squad_data.environments.map(function(env) {
        return "environment=" + env.slug;
    }).join("&")

    // Fetch and parse data from API
    var url = [
        squad_server,
        '/api/data/',
        squad_data.group.slug,
        '/',
        squad_data.project.slug,
        '/?',
        environments_params
    ];

    // Add headers for token authentication.
    var request_options = {};
    if (typeof(request.configParams.token) !== 'undefined') {
        request_options = {
            'headers': {
                'AUTH_TOKEN': request.configParams.token
            }
        }
    }

    var response = UrlFetchApp.fetch(url.join(''), request_options);
    var parsedResponse = JSON.parse(response);

    var requestedData = [];
    for (metric in parsedResponse) {
        for (env in parsedResponse[metric]) {
            var fieldIndex = requestedFieldIds.indexOf(
                env.replace(/-/g, '').replace(/_/g, ''));
            if (fieldIndex != -1) {
                for (i in parsedResponse[metric][env]) {
                    addElementByDate(requestedData, metric,
                                     parsedResponse[metric][env][i], fieldIndex,
                                     dayIndex, requestedFieldIds);
                }
            }
        }
    }

    var rows = requestedData.map(function(elem) {
        if (dayIndex != -1) {
            elem[dayIndex] = (new Date(elem[dayIndex] * 1000)).toISOString().slice(0,10).replace(/-/g, '')
        }
        return { values: elem }
    });
    return {
        schema: requestedFields.build(),
        rows: rows
    };
}
