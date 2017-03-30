<!DOCTYPE html>

<html lang=en>

    <head>
        <title>Turq</title>
        <meta charset=utf-8>
        <!-- Examples are rendered by docutils, and we cannot change
             link targets in there. -->
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
            <header>
                <h1>Turq</h1>
                <p>
                    Mock server is listening on $mock_host port $mock_port —
                    try <a href="$mock_url">$mock_url</a>
                </p>
            </header>
            <form method=POST action=/ target=_self>
                <textarea name=rules accesskey=r
                    cols=79 rows=15>$rules</textarea>
                <div class=submit>
                    <input type=submit name=do value=Install accesskey=i>
                    <div class=status></div>
                    <input type=submit name=do value=Shutdown accesskey=s>
                </div>
            </form>
        </main>
        <aside>
            <h2>Examples</h2>
            $examples
        </aside>
    </body>

</html>
