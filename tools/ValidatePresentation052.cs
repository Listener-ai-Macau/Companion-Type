using System;
using System.Collections.Generic;
using System.Linq;
using System.Web.Script.Serialization;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;
class ValidatePresentation052 {
  static int Main(string[] args) {
    var results=new List<object>(); bool failed=false;
    foreach(string path in args) {
      try {
        using(var doc=PresentationDocument.Open(path,false)) {
          var errors=new OpenXmlValidator(FileFormatVersions.Office2016).Validate(doc).ToList();
          var rows=errors.Take(30).Select(e=>new {description=e.Description,part=e.Part==null?null:e.Part.Uri.ToString(),xpath=e.Path==null?null:e.Path.XPath}).ToList();
          results.Add(new {file=path,errors=errors.Count,details=rows,slides=doc.PresentationPart.SlideParts.Count()});
          if(errors.Count!=0) failed=true;
        }
      }catch(Exception e){results.Add(new {file=path,error=e.ToString()});failed=true;}
    }
    Console.WriteLine(new JavaScriptSerializer().Serialize(results));return failed?1:0;
  }
}
