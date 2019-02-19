// enable popovers that need to trigger on mouse click
$(document).ready(function(){
    $('.popover-regressions-fixes').popover({
        trigger: 'click',
        container: 'body',
        html: true,
        title: function() { return $(this).parent().find('.hidden').attr('title') + '<button type="button" class="close close-popover">&times;</button>' },
        content: function() { return $(this).parent().find('.hidden').html() }
    }).click(function(event) {
        // Prevent parent events triggering.
        event.preventDefault();
    }).on('show.bs.popover', function () {
        // Hide all other popovers.
        $(".popover-regressions-fixes").not(this).popover('hide');
    });

    // Find and simulate click on the button because manully closing popover
    // does not work properly.
    $('body').on("click", ".close-popover", function(event) {
        $('[aria-describedby="' + $(this).parent().parent().attr("id") + '"]').click();
    });

    $('[data-toggle="tooltip"]').tooltip({"trigger": "hover"});
});
