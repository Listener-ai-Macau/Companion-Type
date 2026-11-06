using System;
using System.Collections.Generic;
using System.Linq;
using System.Web.Script.Serialization;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;
class ValidateDocuments054 {
  static int Main(string[] args) {
    var results=new List<object>(); bool failed=false;
    foreach(string path in args) {
      try {
        using(OpenXmlPackage doc=path.EndsWith(".pptx")?(OpenXmlPackage)PresentationDocument.Open(path,false):SpreadsheetDocument.Open(path,false)) {
          var errors=new OpenXmlValidator(FileFormatVersions.Office2016).Validate(doc).ToList();
          results.Add(new {file=path,errors=errors.Count,details=errors.Take(30).Select(e=>new {description=e.Description,part=e.Part==null?null:e.Part.Uri.ToString(),xpath=e.Path==null?null:e.Path.XPath}).ToList()});
          failed|=errors.Count!=0;
        }
      }catch(Exception e){results.Add(new {file=path,error=e.ToString()});failed=true;}
    }
    Console.WriteLine(new JavaScriptSerializer().Serialize(results));return failed?1:0;
  }
}
