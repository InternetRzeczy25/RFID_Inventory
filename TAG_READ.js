var body = ctx_devmac;
for (var i = 0; i < ctx_tagno; i++) {
  body +=
    "|" +
    ctx_tags[i].getEPC() +
    ":" +
    ctx_tags[i].getRSSI() +
    "@" +
    ctx_tags[i].getAntenna() +
    "/" +
    ctx_tags[i].getMux1() +
    "/" +
    ctx_tags[i].getMux2();
}
