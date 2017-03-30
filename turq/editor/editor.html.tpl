<!DOCTYPE html>

<html lang=en>

    <head>
        <title>Turq</title>
        <meta charset=utf-8>
        <!-- Examples are rendered by docutils, and we cannot change
             link targets in there. -->
        <base target=_blank>
    </head>

    <body>
        <h1>Turq</h1>
        <p>Serving on $hostname:$port</p>
        <form method=POST action=/ target=_self>
            <textarea name=rules accesskey=r cols=79 rows=15>$rules</textarea>
            <div>
                <input type=submit name=do value=Install accesskey=i>
                <input type=submit name=do value=Shutdown accesskey=s>
            </div>
        </form>

        <h2>Examples</h2>
        $examples
    </body>

</html>
