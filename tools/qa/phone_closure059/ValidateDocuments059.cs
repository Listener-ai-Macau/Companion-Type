using System;
using System.Collections.Generic;
using System.Linq;
using System.Web.Script.Serialization;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;
class ValidateDocuments059 {
 static int Main(string[] args){var rows=new List<object>();bool failed=false;
  foreach(string path in args){try{
   OpenXmlPackage package;
   switch(System.IO.Path.GetExtension(path)){case ".docx":package=WordprocessingDocument.Open(path,false);break;case ".xlsx":package=SpreadsheetDocument.Open(path,false);break;default:package=PresentationDocument.Open(path,false);break;}
   using(package){var errors=new OpenXmlValidator(FileFormatVersions.Office2016).Validate(package).ToList();rows.Add(new {file=path,errors=errors.Count,details=errors.Take(20).Select(e=>new {description=e.Description,part=e.Part==null?null:e.Part.Uri.ToString(),xpath=e.Path==null?null:e.Path.XPath}).ToList()});failed|=errors.Count!=0;}
  }catch(Exception e){failed=true;rows.Add(new {file=path,error=e.ToString()});}}
  Console.WriteLine(new JavaScriptSerializer().Serialize(rows));return failed?1:0;
 }
}
