# Auditoria jsoup — fontes PT, EN e ES

Auditoria de 13/09/2026. Snapshot: `a1a1d8ccfb31f3fa9c8cf2fab3e4f1cd67071b1f`. Dependência declarada: **1.22.2**. Referência de comparação: **1.14.3**, a última versão anterior à série 1.15; não é uma identificação da versão embarcada no Tachimanga.

## Cobertura

Foram percorridos **1.572 arquivos Kotlin/Java**: 201 em `src/pt`, 642 em `src/en`, 174 em `src/es`, 314 em `src/all`, 170 em `lib-multisrc`, 36 em `lib` e 35 em `core`. `common` não contém arquivos dessas extensões. São 113 módulos PT, 404 EN, 110 ES e 133 multilíngues. Todos os temas compartilhados e módulos multilíngues foram incluídos de forma conservadora, inclusive os que não atendem aos idiomas pedidos.

## Achados confirmados

| Local | Problema | Consequência com 1.14.3 |
|---|---|---|
| [Keyoapp.kt:211](https://github.com/keiyoushi/extensions-source/blob/a1a1d8ccfb31f3fa9c8cf2fab3e4f1cd67071b1f/lib-multisrc/keyoapp/src/eu/kanade/tachiyomi/multisrc/keyoapp/Keyoapp.kt#L211) | Seletor CSS `:is(...)` | `SelectorParseException` |
| [Keyoapp.kt:213](https://github.com/keiyoushi/extensions-source/blob/a1a1d8ccfb31f3fa9c8cf2fab3e4f1cd67071b1f/lib-multisrc/keyoapp/src/eu/kanade/tachiyomi/multisrc/keyoapp/Keyoapp.kt#L213) | Seletor CSS `:is(...)` | `SelectorParseException` |
| [MangaBox.kt:218](https://github.com/keiyoushi/extensions-source/blob/a1a1d8ccfb31f3fa9c8cf2fab3e4f1cd67071b1f/lib-multisrc/mangabox/src/eu/kanade/tachiyomi/multisrc/mangabox/MangaBox.kt#L218) | Seletor CSS `:is(...)` | `SelectorParseException` |
| [BroccoliSoup.kt:130](https://github.com/keiyoushi/extensions-source/blob/a1a1d8ccfb31f3fa9c8cf2fab3e4f1cd67071b1f/src/en/broccolisoup/src/eu/kanade/tachiyomi/extension/en/broccolisoup/BroccoliSoup.kt#L130) | Seletor CSS `:is(...)` | `SelectorParseException` |
| [Mangago.kt:205](https://github.com/keiyoushi/extensions-source/blob/a1a1d8ccfb31f3fa9c8cf2fab3e4f1cd67071b1f/src/en/mangago/src/eu/kanade/tachiyomi/extension/en/mangago/Mangago.kt#L205) | Seletor CSS `:is(...)` | `SelectorParseException` |
| [RagnaScans.kt:118](https://github.com/keiyoushi/extensions-source/blob/a1a1d8ccfb31f3fa9c8cf2fab3e4f1cd67071b1f/src/es/ragnascans/src/eu/kanade/tachiyomi/extension/es/ragnascans/RagnaScans.kt#L118) | `Elements.selectFirst(String)` em `infoWrap` | Método ausente; risco de `NoSuchMethodError` |
| [RagnaScans.kt:119](https://github.com/keiyoushi/extensions-source/blob/a1a1d8ccfb31f3fa9c8cf2fab3e4f1cd67071b1f/src/es/ragnascans/src/eu/kanade/tachiyomi/extension/es/ragnascans/RagnaScans.kt#L119) | `Elements.selectFirst(String)` em `infoWrap` | Método ausente; risco de `NoSuchMethodError` |

São **7 pontos em 5 arquivos**: duas chamadas em Ragna Scans, um seletor em Broccoli Soup, um em Mangago, dois em Keyoapp e um em MangaBox. Os testes reproduziram a rejeição dos quatro formatos de seletor também em **1.15.1**; em **1.22.2**, todos foram aceitos.

**Correção do contexto inicial:** `Elements.selectFirst(String)` foi introduzido em **1.19.1**, conforme `@since` do código oficial, e não em 1.15. `Element.selectFirst(String)` já existe em 1.14.3. Não se deve substituir indiscriminadamente toda chamada com esse nome.

### Módulos que herdam os seletores

- **keyoapp (17 módulos):** `en/artlapsa`, `en/asmotoon`, `en/erisscans`, `en/grimscans`, `en/kaizenscan`, `en/kewnscans`, `en/lunatoons`, `en/meitoon`, `en/mistscans`, `en/nyanukafe`, `en/nyrascans`, `en/paradisescans`, `en/ritharscans`, `en/sirenscans`, `en/suryascans`, `en/timelesstoons`, `en/writerscans`.
- **mangabox (3 módulos):** `en/mangabat`, `en/mangakakalot`, `en/manganelo`.

Os consumidores listados não sobrescrevem o seletor problemático correspondente. Isso eleva o alcance potencial a **23 módulos**: Ragna Scans, Broccoli Soup, Mangago e 20 consumidores de temas. Trata-se de incompatibilidade do caminho de código herdado, sem teste de funcionamento dos sites ou instalação no iOS. Não foi confirmado outro uso de API nova nas fontes PT nesta análise; isso não certifica sua compatibilidade geral.

## Triagem e limites

- Comparação das assinaturas públicas de todas as classes dos JARs oficiais usando `javap`, seguida de busca lexical das APIs adicionadas/alteradas nos arquivos do escopo. O catálogo inclui sobrecargas, construtores e nomes coincidentes; o JSON bruto contém falsos positivos.
- `wholeOwnText`, `expectFirst`, `selectStream`, `selectNodes`, `selectFirstNode`, `expectFirstNode`, `sourceRange`, `endSourceRange`, `nodeStream` e outros nomes novos foram cobertos pelo catálogo. Não surgiram chamadas confirmadas adicionais dessas APIs.
- **Mehgazone** já implementa `Elements.selectFirstBackport`, usando `QueryParser.parse` e `Collector.findFirst`; não chama o método novo de Elements.
- **IRovedOut** foi descartado na triagem: `chapterWrap` é um Element, tanto após `selectFirst` quanto após `select(...).find`. O detector lexical sinaliza esse caso, mas a operação terminal muda o tipo.
- `Element.normalName`, `Element.selectXpath`, `tagName()` sem argumentos, `tag()` e métodos antigos herdados não devem ser classificados como novos só porque aparecem no diff de outra classe/sobrecarga. Ocorrências de `newRequest` em KuroMangas são funções locais.
- Esta é uma varredura estática com triagem e provas focadas, não resolução completa de tipos Kotlin. Não garante ausência de chamadas indiretas, reflexão, APIs de dependências externas ou código gerado. Não foi feita compilação dos APKs nem validação no Tachimanga. Uma versão embarcada anterior a 1.14.3 pode ter outras incompatibilidades.

## Correções recomendadas

Em Ragna Scans, trocar as duas chamadas de `infoWrap.selectFirst(query)` por `infoWrap.select(query).firstOrNull()`. Isso preserva a busca em todos os elementos e o resultado nulo quando não há correspondência.

Para `:is(...)`, expandir em grupos separados por vírgula, repetindo os prefixos/sufixos e filtros para cada alternativa. Exemplo: `section > :is(h1, h2)` vira `section > h1, section > h2`. Em Keyoapp é necessário manter os filtros de capítulos pagos e Upcoming em ambos os ramos; em MangaBox manter `:has(a[data-id])` em ambos. Não basta remover o `:is`.

A auditoria não alterou as extensões nem publicou APKs.

## Repetir

Na raiz do workspace:

```powershell
python audit_jsoup.py --javap 'C:/Program Files/Java/jdk-25.0.3/bin/javap.exe'
```

O script lê a versão jsoup declarada no checkout, baixa os JARs necessários do Maven Central e produz `inventory.json`, `api-diff.json`, `candidates.json` e `focused.json`. Os achados do detector exigem revisão; este relatório contém a triagem do snapshot acima.

As provas executáveis estão em `JsoupProbe.java`; os resultados em `probe-1.14.3.txt`, `probe-1.15.1.txt` e `probe-1.22.2.txt`. O teste usa reflexão para verificar a presença exata do método, analisa os seletores e exercita a alternativa antiga sobre múltiplos elementos. A alternativa devolveu `Autor: A` nas três versões.

## Referências primárias

- [Código de Elements no jsoup 1.22.2, incluindo @since 1.19.1](https://github.com/jhy/jsoup/blob/jsoup-1.22.2/src/main/java/org/jsoup/select/Elements.java).
- [Artefatos oficiais do jsoup no Maven Central](https://repo.maven.apache.org/maven2/org/jsoup/jsoup/).
