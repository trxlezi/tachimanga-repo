import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.select.Elements;
public class SelectorRegression {
 static final String HTML = "<section><h4 id='h4'>D</h4><h1 id='h1'>A</h1><h3 id='h3'>C</h3><h2 id='h2'>B</h2><h5>X</h5></section>"
  + "<table id='raws_table'><tr id='r1'><td>A</td></tr></table><table id='chapter_table' class='uk-table'><tr id='r2'><td>B</td></tr></table><table class='uk-table'><tr id='r3'><td>C</td></tr></table>"
  + "<div id='chapters'><a id='free'>Free</a><div id='paid'><img alt='Coin'></div><div id='upcoming'><div class='text-sm'><span>Upcoming</span></div></div><a id='free2'>Free 2</a><p>Ignore</p></div>"
  + "<div class='truyen-list'><div class='list-truyen-item-wrap' id='m1'><a data-id='1'>A</a></div><div class='list-truyen-item-wrap'>Ignore</div></div>"
  + "<div class='comic-list'><div class='list-comic-item-wrap' id='m2'><a data-id='2'>B</a></div><div class='list-comic-item-wrap'>Ignore</div></div>";
 static final String[][] PAIRS = {
  {"section > :is(h1, h2, h3, h4)", "section > h1, section > h2, section > h3, section > h4"},
  {":is(table#raws_table, table#chapter_table) > tbody > tr, table.uk-table > tbody > tr", "table#raws_table > tbody > tr, table#chapter_table > tbody > tr, table.uk-table > tbody > tr"},
  {"#chapters > :is(a, div):not(:has(.text-sm span:matches(Upcoming)))", "#chapters > a:not(:has(.text-sm span:matches(Upcoming))), #chapters > div:not(:has(.text-sm span:matches(Upcoming)))"},
  {"#chapters > :is(a, div):not(:has(.text-sm span:matches(Upcoming))):not(:has(img[alt~=Coin]))", "#chapters > a:not(:has(.text-sm span:matches(Upcoming))):not(:has(img[alt~=Coin])), #chapters > div:not(:has(.text-sm span:matches(Upcoming))):not(:has(img[alt~=Coin]))"},
  {":is(div.truyen-list > div.list-truyen-item-wrap, div.comic-list > .list-comic-item-wrap):has(a[data-id])", "div.truyen-list > div.list-truyen-item-wrap:has(a[data-id]), div.comic-list > .list-comic-item-wrap:has(a[data-id])"}
 };
 public static void main(String[] args) {
  Document doc=Jsoup.parse(HTML);
  boolean modern=args[0].equals("modern");
  String[] expected={"[h4, h1, h3, h2]", "[r1, r2, r3]", "[free, paid, free2]", "[free, free2]", "[m1, m2]"};
  for(int i=0;i<PAIRS.length;i++) {
   String found=doc.select(PAIRS[i][modern?0:1]).eachAttr("id").toString();
   if(!found.equals(expected[i])) throw new AssertionError(i+":"+found);
   System.out.println(i+":"+found);
  }
  Elements roots=Jsoup.parse("<div><span>Other</span></div><div><span>Autor: Alice</span><span>Ilustrador: Bob</span></div>").select("div");
  if(!roots.select("span:contains(Autor:)").first().text().equals("Autor: Alice")) throw new AssertionError();
  if(!roots.select(".missing").isEmpty()) throw new AssertionError();
  System.out.println("Ragna: multiple roots and absent matches OK");
 }
}
