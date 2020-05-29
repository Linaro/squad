function viewShowHide(anchor_id, target_id){
    var showHide=document.getElementById(anchor_id);
    var target=document.getElementById(target_id);
    if (showHide.innerHTML=="»") {
        showHide.innerHTML="«";
        $(target).toggle();
        return false;
    } else {
        showHide.innerHTML="»";
        $(target).toggle();
        return false;
    }
}

