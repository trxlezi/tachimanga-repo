import org.jsoup.Jsoup;
import org.jsoup.select.Elements;
public class JsoupProbe {
 public static void main(String[] args) throws Exception {
  try { Elements.class.getMethod("selectFirst", String.class); System.out.println("Elements.selectFirst: PRESENT"); }
  catch (NoSuchMethodException e) { System.out.println("Elements.selectFirst: ABSENT"); }
  for (String q : new String[]{"section > :is(h1, h2, h3, h4)", ":is(table#raws_table, table#chapter_table) > tbody > tr, table.uk-table > tbody > tr", "#chapters > :is(a, div):not(:has(.text-sm span:matches(Upcoming)))", ":is(div.truyen-list > div.list-truyen-item-wrap, div.comic-list > .list-comic-item-wrap):has(a[data-id])"}) {
   try { Jsoup.parse("<section><h1>test</h1></section>").select(q); System.out.println("OK " + q); }
   catch (Exception e) { System.out.println(e.getClass().getSimpleName()+" "+q); }
  }
  var roots=Jsoup.parse("<div class='info'><span>Autor: A</span></div><div class='info'><span>Ilustrador: B</span></div>").select(".info");
  System.out.println("Backport: " + roots.select("span:contains(Autor:)").first().text());
 }
}
