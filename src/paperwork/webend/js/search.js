$(function() {
    $("#searchbox").keyup(function () {
        var term = $("#searchbox").val();
        $.get("search", {term:term}, function (documents) {
            //var documents = JSON.parse(data);
            $("#search-suggestions").html("");
            for (var i = 0; i < documents.files.length; i++)
            {
                $("#search-suggestions").append(
                    "<div class=\"document-list-item\">"
                        + "<h4>"
                        + documents.files[i].name +
                        + "</h4>"
                        + "<i class=\"material-icons md-dark file-launcher\" "
                        + "onclick=\"filelaunch(this)\" data-file-path=\""
                        + documents.files[i].id + "/doc.pdf\">call_made</i>"
                        + "</div>");
            }
        });
    });

    $("#searchbox").keyup();
});
