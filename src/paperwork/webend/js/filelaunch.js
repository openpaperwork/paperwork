function filelaunch(obj)
{
    $("#pdfviewer").attr("src", "pages/web/viewer.html?file="+obj.dataset.filePath);
}
