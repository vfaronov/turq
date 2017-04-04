/* jshint browser: true, -W097, -W040 */
/* globals CodeMirror */

'use strict';


var codeMirror = null;


function installCodeMirror() {
    var textArea = document.querySelector('textarea');
    codeMirror = CodeMirror.fromTextArea(textArea, {
        lineNumbers: true,
        indentUnit: 4,
        extraKeys: {
            Tab: 'insertSoftTab'    // insert spaces when Tab is pressed
        }
    });
    CodeMirror.colorize(document.querySelectorAll('aside pre'), 'python');
}


function interceptForm() {
    document.forms[0].addEventListener('submit', function (e) {
        e.preventDefault();
        hideStatus();
        // Send more or less the same data, but via XHR.
        var req = new XMLHttpRequest();
        req.onreadystatechange = onReadyStateChange;
        codeMirror.save();
        var data = new FormData(this);
        // https://blog.yorkxin.org/2014/02/06/ajax-with-formdata-is-broken-on-ie10-ie11
        data.append('workaround', 'IE');
        req.open(this.method, this.action);
        req.timeout = 5000;
        req.send(data);
        codeMirror.focus();
    });
}


function onReadyStateChange() {
    if (this.readyState !== 4) return;       // not DONE yet
    var text;
    var type = (this.getResponseHeader('Content-Type') || '').toLowerCase();
    if (type.indexOf('text/plain') === 0) {
        text = this.responseText;
    } else if (this.status) {
        text = this.statusText;
    } else {
        text = 'Connection error';
    }
    var isError = !this.status || (this.status >= 400);
    displayStatus(text, isError);
}


var timeoutId = null;


function displayStatus(text, isError) {
    if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
    }
    var status = document.querySelector('.status');
    status.textContent = text;
    if (isError) {
        status.classList.add('error');
    } else {
        status.classList.remove('error');
        // An "okay" message is safe to hide after a short delay.
        timeoutId = window.setTimeout(hideStatus, 1000);
    }
}


function hideStatus() {
    document.querySelector('.status').textContent = '';
    timeoutId = null;
}


document.addEventListener('DOMContentLoaded', function() {
    document.querySelector('textarea').focus();
    installCodeMirror();
    interceptForm();
});
