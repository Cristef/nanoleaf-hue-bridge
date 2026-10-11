# Prima pubblicazione

Questa cartella va pubblicata come radice di un repository indipendente.
Non pubblicare la cartella superiore del progetto originale.

## Verificato localmente

- 23 test Python passati (HomeKit, REST, discovery, decoder, configurazione e wizard).
- SintassiBash dei due installer verificata, senza esecuzione dei comandi apt.
- Sorgenti compilati; nessun IP/MAC, identificativo areaHue o percorso personale
  dell'installazione originaria presente nei sorgenti pubblici.
- Copiati solo file di codice con elenco esplicito; niente token, PIN, privatekey,
  datiHomeKit, catture o snapshot del container operativo.

## Da verificare su un secondo LXC

1. Debian12 nuovo, stessaLAN, console root e indirizzi stabili.
2. Eseguire install.sh; aggiornamentiOS, librerie e account senza interventi tecnici.
3. Selezionare dispositivi/IP/MAC, codiceHomeKit e abbinamento reale.
4. PulsanteHue, selezione fra aree multimediali e prova sulle luci.
5. Acceso/spento del virtuale, arresto flusso, crash e riavvio del nuovoCT.
6. Interrompere e riprendere il wizard: nessuna rigenerazione delle chiavi.
7. Cambioarea e disattivazione con ripristino del percorsoShapes.

Usare il nuovo virtuale solo quando il ponte originario e disattivato: due relay
ARP simultanei per la stessa coppia di dispositivi interferirebbero fra loro.
La creazione/abilitazione del nuovoCT avviene in Proxmox, fuori dall'installer.

## Pubblicazione

- Repository privato Cristef/nanoleaf-hue-bridge, branchmain e licenza PolyForm Noncommercial 1.0.0.
- Comando README aggiornato; download anonimo utilizzabile solo dopo il passaggio a pubblico.
- Pubblicare inizialmente come versione sperimentale e registrare gli impianti
  realmente verificati, senza dichiarare supporto universale o funzionamento
  senzaShapes.
- Lasciare eseguire la CI e aggiungere al changelog il testDebian12 reale.

## License review

- Dependency licenses and original notices reviewed; see LICENSE_AUDIT.md.
- Before public release, remove earlier MIT revisions from published refs,
  retaining a private local backup. Previously granted MIT rights cannot be revoked.
- A prebuilt container requires a separate dependency and OS redistribution review.
