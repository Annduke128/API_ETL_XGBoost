name := "retail-spark-etl"

version := "1.0.0"

scalaVersion := "2.12.17"

val sparkVersion = "3.5.0"

libraryDependencies ++= Seq(
  // Spark Core
  "org.apache.spark" %% "spark-core" % sparkVersion % "provided",
  "org.apache.spark" %% "spark-sql" % sparkVersion % "provided",
  
  // JDBC Drivers
  "org.postgresql" % "postgresql" % "42.7.1",
  "com.clickhouse" % "clickhouse-jdbc" % "0.5.0",
  
  // Configuration
  "com.typesafe" % "config" % "1.4.3",
  
  // Logging
  "org.apache.logging.log4j" % "log4j-core" % "2.22.1",
  
  // Testing
  "org.scalatest" %% "scalatest" % "3.2.17" % Test
)

// Assembly settings for fat JAR
assembly / assemblyMergeStrategy := {
  case PathList("META-INF", xs @ _*) => xs match {
    case "MANIFEST.MF" :: Nil => MergeStrategy.discard
    case _ => MergeStrategy.discard
  }
  case "reference.conf" => MergeStrategy.concat
  case x => MergeStrategy.first
}

assembly / assemblyOption := (assembly / assemblyOption).value.copy(includeScala = false)

// Spark run settings
fork := true

javaOptions ++= Seq(
  "-Xms2G",
  "-Xmx4G",
  "-XX:+UseG1GC"
)
