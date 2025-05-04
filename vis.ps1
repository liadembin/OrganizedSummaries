docker run `
--mount type=bind,source="${PWD}",target=/home/schcrwlr `
--rm -it `
schemacrawler/schemacrawler `
/opt/schemacrawler/bin/schemacrawler.sh `
--server=sqlite `
--database=dbconved.db `
--info-level=standard `
--command=schema `
--output-file=output.png
