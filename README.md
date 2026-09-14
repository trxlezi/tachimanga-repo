# Extensões pessoais para Tachimanga

Recompilações locais do [Keiyoushi extensions-source](https://github.com/keiyoushi/extensions-source), com correções de jsoup, `minSdk 21`, sem minificação/R8/ProGuard do bytecode e assinatura própria permanente. **As verificações são de build e APK; ainda é necessário testar no Tachimanga/iOS.**

Repositório: https://github.com/trxlezi/tachimanga-repo

## Instalação e acesso ao índice

Endereço do índice:

```text
https://raw.githubusercontent.com/trxlezi/tachimanga-repo/main/index.min.json
```

**O repositório foi criado privado, conforme solicitado. Essa URL exige autenticação e não funciona como um endereço público para colar no app.** Não há token embutido no índice. A publicação sem autenticação depende de autorização para tornar o repositório público ou escolher outra forma de distribuição. Tokens temporários dos botões Raw do GitHub não são uma solução permanente.

Quando o índice estiver acessível pelo app:

1. Faça um backup da biblioteca no Tachimanga.
2. Desinstale a extensão oficial correspondente, pois a assinatura deste repositório é diferente. Não exclua os mangás da biblioteca.
3. Em Browser → Extensions → `+`, adicione a URL do índice e instale a extensão pessoal. Confirme a confiança na assinatura própria se solicitado.
4. Comece por **Ragna Scans 1.4.3**: abra detalhes, lista de capítulos e um capítulo. Confira autor e ilustrador.

IDs de fonte e nomes permanecem iguais aos oficiais. O ID de Ragna Scans é `6003330990591348231`.

## Conteúdo e correções

Há **23 APKs** no índice. A lista completa e os resultados estão em [verification/RESUMO.md](verification/RESUMO.md).

- Ragna Scans: `Elements.selectFirst(q)` substituído por `select(q).firstOrNull()` em autor e ilustrador.
- Broccoli Soup e Mangago: expansão de `:is(...)` em seletores antigos equivalentes.
- Keyoapp (17 extensões) e MangaBox (3 extensões): mesma expansão, preservando filtros, ordem do documento e eliminação de duplicatas.
- Mangago e Keyoapp: leitura de datas com `SimpleDateFormat` para atender ao mínimo Android 21; UTC preservado em Mangago e acesso sincronizado ao formatador.
- Versões incrementadas nas três extensões individuais e nas duas bases compartilhadas.

`Elements.selectFirst(String)` surgiu no jsoup **1.19.1**. Não confundir com `Element.selectFirst(String)`, já existente na referência 1.14.3. Os seletores foram testados em 1.14.3, 1.15.1 e 1.22.2.

O compilador atual do Keiyoushi gera um ponto de entrada chamado `Generated` mesmo sem R8. Neste perfil ele foi nomeado explicitamente `keiyoushi.source.TachimangaEntryPoint`, e o manifest aponta para ele; as classes originais das extensões continuam no APK. Não se trata de patch de smali.

**Limites:** 2 extensões usam API/lib 1.4 e 21 usam 1.6. Corrigir jsoup e as opções de build não comprova que toda a API 1.6, bibliotecas fornecidas pelo app ou o verificador OpenJ9 sejam compatíveis com a versão instalada do Tachimanga. Não foi realizado teste no iOS nem uma varredura de todas as APIs de dependências. Se o app apresentar outro erro, registre a exceção completa antes de instalar mais extensões.

## Chave de assinatura

A chave foi gerada uma única vez, em `keystore/tachimanga.jks`, com as senhas em `keystore/keystore.properties`. **A pasta inteira está ignorada pelo Git e não foi enviada ao GitHub.** Faça um backup seguro dessa pasta: sem ela não será possível assinar atualizações com a mesma identidade. Nunca gere outra chave para substituir a atual.

O certificado público e sua impressão SHA-256 estão em `signing-certificate.der` e `signing-certificate.sha256`. O verificador rejeita APKs assinados por outra chave. A assinatura inclui os esquemas v1 e v2.

## Recompilar uma extensão

Requisitos: Python 3, Git, JDK compatível com Gradle 9.7.1 (neste build, JDK 25), Android SDK Platform 37.0 e build-tools 37.0.0. Configure `JAVA_HOME` e `ANDROID_HOME`. No Windows, o script também procura o JDK em `C:/Program Files/Java` e o SDK no diretório padrão do usuário.

```bash
./add-extension.sh es ragnascans
```

Ou, diretamente no PowerShell:

```powershell
python add_extension.py es ragnascans
```

O script:

1. Obtém o código do commit fixado `a1a1d8ccfb31f3fa9c8cf2fab3e4f1cd67071b1f` e aplica `patches/tachimanga.patch`, sem descartar modificações existentes.
2. Reutiliza a chave original e calcula uma versão superior às versões publicada localmente e oficial, incluindo a versão-base do tema.
3. Compila o release e executa lint da extensão e de seu tema direto.
4. Verifica o APK com aapt2, apksigner, dexdump e inspeção dos IDs de métodos do DEX.
5. Copia APK, ícone e metadados, arquiva versões anteriores em `build/previous-apks`, atualiza o índice e exporta as alterações para o patch.

O script **não inventa correções para APIs desconhecidas**, não atualiza o checkout upstream automaticamente e não faz commit/push. Um nome de diretório pode divergir do nome exibido no app. Para uma fonte nova que quebre: erro → localizar chamada no código → aplicar equivalente antigo → executar o script → revisar → commit/push.

Em outra máquina, restaure a pasta `keystore/` antes do primeiro build. O script recusa a substituição da identidade de assinatura. Para atualizar o commit upstream, rebaseie o patch e atualize `BASE` em `add_extension.py`; não force reset sobre alterações locais.

## Índice e manutenção

```powershell
python build_index.py
python build_index.py --offline
python verify_apk.py apk/tachiyomi-es.ragnascans-v1.4.3.apk
python -m unittest discover -s tests -v
```

`build_index.py` lê versão, pacote e minSdk reais via aapt2; compara os metadados gerados pelo build com os IDs exatos do `index.pb` oficial (protobuf gzipado). Não passa IDs por ponto flutuante. Divergências e metadados ausentes abortam a geração, preservando o índice anterior.

`code` é o último componente da versão (`3` para `1.4.3`), não o versionCode Android codificado (`104003`). `versionId` vem da declaração da fonte, e não é incrementado ao corrigir uma extensão.

Se o Tachimanga exigir a extensão de arquivo `.jar`:

```powershell
python build_index.py --jar-alias
```

Essa opção cria cópias byte a byte dos APKs com nome `.jar` e muda o índice. **Não são os JARs JVM otimizados que o Keiyoushi também produz atualmente.** Não use `-PoptimizedExtensionJar=true` neste perfil: esse caminho upstream usa ProGuard.

```powershell
git add README.md index.min.json apk icon metadata verification patches
git commit -m 'Update personal extensions'
git push origin main
```

Os arquivos de código upstream ficam no checkout ignorado `extensions-source/`; suas mudanças ficam versionadas no patch. Downloads, cache oficial, logs e senhas não entram no repositório. Não use `git add -f` na pasta de chaves.

## Evidências

- [Auditoria inicial](audit/RELATORIO.md)
- [Teste de equivalência dos seletores](audit/selector-regression.txt)
- [Resultados de todos os APKs](verification/RESUMO.md)
- [Formato do índice documentado pelo Tachimanga](https://tachimanga.app/help/guides/repositories.html)

Código upstream sob a licença incluída em [LICENSE](LICENSE).
