var show_dropdown = {};
function toggle_drop_down(button_id, menu_id) {
    show_dropdown[menu_id] = !show_dropdown[menu_id];
    var dropdown = document.getElementById(menu_id);
    if (show_dropdown[menu_id]) {

        var bodyRect = document.body.getBoundingClientRect();
        var buttonRect = document.getElementById(button_id).getBoundingClientRect();
        var offset = bodyRect.right - buttonRect.right;

        dropdown.style.right = offset;
        dropdown.style.display = 'block';
    } else {
        dropdown.style.display = '';
    }
}

