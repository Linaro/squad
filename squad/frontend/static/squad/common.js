// enable popovers that need to trigger on mouse hovers
$(document).ready(function(){
    $('.popover-hover').popover({
            trigger: 'hover',
            container: 'body',
            html: true,
            title: function() { return $(this).parent().find('.hidden').attr('title') },
            content: function() { return $(this).parent().find('.hidden').html() }
    });
});

