# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - heading "Simple Social" [level=1] [ref=e2]
  - generic [ref=e3]:
    - heading "Post erstellen" [level=2] [ref=e4]
    - generic [ref=e5]:
      - generic [ref=e6]: Bild
      - button "Bild" [ref=e7]
      - generic [ref=e8]: Text
      - textbox "Text" [ref=e9]:
        - /placeholder: Schreibe etwas...
      - generic [ref=e10]:
        - button "Kommentar vorschlagen" [ref=e11] [cursor=pointer]
        - button "Übernehmen" [disabled] [ref=e12] [cursor=pointer]
        - button "Vorschlag verwerfen" [disabled] [ref=e13] [cursor=pointer]
      - generic [ref=e14]: User
      - textbox "User" [ref=e15]:
        - /placeholder: alice
        - text: alice
      - button "Post erstellen" [ref=e16] [cursor=pointer]
  - generic [ref=e17]:
    - heading "Posts" [level=2] [ref=e18]
    - generic [ref=e19]:
      - button "Alle neu laden" [ref=e20] [cursor=pointer]
      - generic [ref=e21]: "Filter by user:"
      - textbox "alice" [ref=e22]
      - button "Search" [ref=e23] [cursor=pointer]
      - button "Clear" [ref=e24] [cursor=pointer]
```