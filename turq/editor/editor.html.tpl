<!DOCTYPE html>

<html lang=en>

    <head>
        <title>Turq</title>
        <meta charset=utf-8>
        <!-- Examples are rendered by docutils, and we cannot change
             link targets in there, so use a `base`. -->
        <base target=_blank>
        <link rel=stylesheet href=/static/codemirror/lib/codemirror.css>
        <link rel=stylesheet href=/static/editor.css>
        <script src=/static/codemirror/lib/codemirror.js></script>
        <script src=/static/codemirror/mode/python/python.js></script>
        <script src=/static/codemirror/addon/runmode/runmode.js></script>
        <script src=/static/codemirror/addon/runmode/colorize.js></script>
        <script src=/static/editor.js></script>
    </head>

    <body>
        <main>
            <h1>Turq</h1>
            <p>
                Mock server is listening on $mock_host port $mock_port —
                try <a href="$mock_url">$mock_url</a>
            </p>
            <!-- `target` necessary here to override the `base` -->
            <form method=POST action=/editor target=_self>
                <textarea name=rules cols=79 rows=15>$rules</textarea>
                <p class=submit>
                    <input type=submit name=do value=Install accesskey=i>
                    <span class=status></span>
                </p>
            </form>
        </main>
        <aside>
            <h2>Examples</h2>
            $examples
        </aside>
    </body>

</html>
