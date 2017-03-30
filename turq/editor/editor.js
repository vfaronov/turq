/* jshint browser: true, -W097 */
/* globals CodeMirror */

'use strict';


function installCodeMirror() {
    var textArea = document.querySelector('form textarea');
    CodeMirror.fromTextArea(textArea, {
        lineNumbers: true,
        indentUnit: 4
    });
    CodeMirror.colorize(document.querySelectorAll('aside pre'), 'python');
}


document.addEventListener('DOMContentLoaded', function() {
    document.querySelector('form textarea').focus();
    installCodeMirror();
});
