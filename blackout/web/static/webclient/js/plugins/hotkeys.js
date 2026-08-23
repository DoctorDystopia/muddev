// https://github.com/evennia/evennia/wiki/Webclient/ed3b33720b3c31f289c4b6d0c1313829f4df805f


// test plugin for hotkeys to control movement, work in progress

// might be global? look into how javascript handles scope]

// when dealing with or changing the webclient stuff,
// 1) evennia stop
// 2) evennia collectstatic
// 3) evennia start

var hotkeys = (function () {
    var keymap = {
        "w": "north",
        "a": "west",
        "s": "south",
        "d": "east",
        "q": "northwest",
        "e": "northeast",
        "z": "southwest",
        "c": "southeast",
        "k": "north",
        "h": "west",
        "j": "south",
        "l": "east",
        "y": "northwest",
        "u": "northeast",
        "b": "southwest",
        "n": "southeast",
    }

    // boolean onKeydown(event) This plugin listens for Keydown events
    var onKeydown = function (event) {
        // browser tag rules
        // https://developer.mozilla.org/en-US/docs/Web/API/Element/tagName
        // https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements

        var active = document.activeElement;
        var typing = false;

        if (active) {
            typing = active.tagName === "TEXTAREA" || active.tagName === "INPUT";
        }

        // if typing in the input pane, don't handle hotkeys
        if (typing) {
            return false;
        }

        var cmd = keymap[event.key];
        if (cmd) {
            Evennia.msg("text", [cmd], {});
            event.preventDefault(); // Without event.preventDefault(), pressing arrow keys to move your character north would also scroll the webclient console up
            return true;
        }
        return false;
    };

    let init = function () {
        console.log("hotkeys script found! Hello World!");
    }

    return {
        init: init,
        onKeydown: onKeydown,
    }
})();
plugin_handler.add("hotkeys", hotkeys);