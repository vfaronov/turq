<!DOCTYPE html>

<html>

    <head>
        <title>Turq</title>
        <meta charset=utf-8>
    </head>

    <body>
        <h1>Turq</h1>
        <p>Serving on $hostname:$port</p>
        <form method=POST action=/>
            <textarea name=rules accesskey=r cols=79 rows=15>$rules</textarea>
            <div>
                <input type=submit name=do value=Install accesskey=i>
                <input type=submit name=do value=Shutdown accesskey=s>
            </div>
        </form>
    </body>

</html>
