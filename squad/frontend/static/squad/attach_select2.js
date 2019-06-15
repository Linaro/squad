export function attach_select2($http) {
    var page_size = 20
    var ngAjax = function(params, success) {
        var url = params.url + '?' + $.param(params.data)
        var request = $http.get(url)
        request.then(success)
        return request
    }

    return function(url, element, value_field, filters) {
        element.select2({
            minimumInputLength: 0,
            placeholder: element.attr('placeholder'),
            ajax: {
                transport: ngAjax,
                url: url,
                dataType: 'json',
                data: function (params) {
                    var term = params.term == undefined ? '' : params.term
                    var queryString = filters(term)
                    queryString['limit'] = page_size
                    queryString['offset'] = params.page * page_size || 0
                    queryString['page'] = params.page
                    return queryString
                },
                processResults: function (data, params) {
                    params.page = params.page || 0
                    var r = data.data.results
                    for(var item in r){
                        r[item].text = r[item][value_field];
                        r[item].id = r[item][value_field];
                    }
                    return {
                        results: r,
                        pagination: { more: ((params.page + 1) * page_size) < data.count }
                    };
                }
            }
        })
    }
}
