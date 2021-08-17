package spatialAnalysis;

import java.awt.Shape;
import java.util.ArrayList;
//import java.util.Map;

//import org.jgrapht.Graph;
//import org.jgrapht.alg.scoring.BetweennessCentrality;

import edu.sc.geography.data.ReadCSVFile;
import edu.sc.geography.networkMeasures.ConstructDirectedWeightedJGraphFromFlowData;
import edu.sc.geography.networkMeasures.NodeMeasureSI_BasicMeasures;
import edu.sc.geography.networkMeasures.NodeMeasureSI_Entropy_Smoothed;
import edu.sc.geography.networkMeasures.NodeMeasureSI_GiniIndex;
import edu.sc.geography.networkMeasures.PrepareFlowData;
import edu.ui.utils.FolderUtils;

public class CalculateNetworkMeasuresForWeb {

	String[] varnames = new String[] { "TotalFlow", "Inflow", "Outflow", "Netflow", "NetflowRatio", "Entropy",
			"InflowEntropy", "OutflowEntropy", "Gini", "InGini", "OutGini", "WithinFlow", "Degree",
			"InDegree", "OutDegree" };

	private static final int TOTALFLOW = 0, INFLOW = 1, OUTFLOW = 2, NETFLOW = 3, NETFLOWRATIO = 4, ENT = 5,
			INFLOWENT = 6, OUTFLOWENT = 7, GINI = 8, INGINI = 9, OUTGINI = 10, WITHINFLOW = 11,
			DEGREE = 12, INDEGREE = 13, OUTDEGREE = 14;

	float[] totalflow, inflow, outflow, netflow, netflowratio, ent, entIn, entOut, gini, giniIn, giniOut, withinflow,
			betweennessNormalized, degree, indegree, outdegree;

	private Shape[] shps = null;

	private PrepareFlowData flowD = null;
	private ArrayList<float[]> measureResults = new ArrayList<float[]>();
	
	//added for result
	public String outputString = "";

	public CalculateNetworkMeasuresForWeb(String flowCSVString) {
		
		flowD = new PrepareFlowData(flowCSVString, true);
		float[][] flowTable = flowD.getFlowtable();

		NodeMeasureSI_BasicMeasures basicMeasures = new NodeMeasureSI_BasicMeasures(flowTable);
		totalflow = basicMeasures.getStrength();
		inflow = basicMeasures.getInflow();
		outflow = basicMeasures.getOutflow();
		netflow = basicMeasures.getNetFlow();
		netflowratio = basicMeasures.getNetFlowRatio();
		withinflow = basicMeasures.getWithinUnitFlows();
		degree = basicMeasures.getDegree();
		indegree = basicMeasures.getInDegree();
		outdegree = basicMeasures.getOutDegree();

		NodeMeasureSI_Entropy_Smoothed entropySM = new NodeMeasureSI_Entropy_Smoothed(flowTable);
		ent = entropySM.calculateEntropy(1);
		entIn = entropySM.calculateEntropy(2);
		entOut = entropySM.calculateEntropy(3);

		NodeMeasureSI_GiniIndex giniIndex = new NodeMeasureSI_GiniIndex(flowTable);
		gini = giniIndex.calculateGiniIndex();
		giniIn = giniIndex.calculateInGiniIndex();
		giniOut = giniIndex.calculateOutGiniIndex();

//		boolean weighted = true;
//		boolean directed = true;
//		boolean normalize = true;
//		ConstructDirectedWeightedJGraphFromFlowData jgrapht = new ConstructDirectedWeightedJGraphFromFlowData(flowCSV,
//				weighted, directed);
//		Graph graph = jgrapht.getGraph();
//		String ids[] = flowD.getIDs();

//		BetweennessCentrality bcn = new BetweennessCentrality(graph, normalize);
//		Map<String, Double> nodesn = bcn.getScores();
//		betweennessNormalized = new float[totalflow.length];
//		for (int i = 0; i < ids.length; i++) {
//			Double val = nodesn.get(ids[i]);
//			betweennessNormalized[i] = val.floatValue();
//		}

		for (int mm = 0; mm < varnames.length; mm++) {
			float[] measureResult = setUnitMeasureResults(mm);
			measureResults.add(measureResult);
		}
		
//		String path = FolderUtils.extractFolderPath(flowCSV);
		exportMeasures("NO NEED FOR THIS ARGUMENT");
	}

	private float[] setUnitMeasureResults(int measure) {
		switch (measure) {
		case DEGREE:
			return degree;
		case INDEGREE:
			return indegree;
		case OUTDEGREE:
			return outdegree;
		case TOTALFLOW:
			return totalflow;
		case INFLOW:
			return inflow;
		case OUTFLOW:
			return outflow;
		case NETFLOW:
			return netflow;
		case NETFLOWRATIO:
			return netflowratio;
		case INGINI:
			return giniIn;
		case OUTGINI:
			return giniOut;
		case GINI:
			return gini;
		case INFLOWENT:
			return entIn;
		case OUTFLOWENT:
			return entOut;
		case ENT:
			return ent;
		case WITHINFLOW:
			return withinflow;
		}
		return null;
	}

	private void exportMeasures(String outputFile) {
		float[] m0 = measureResults.get(0);
		float[][] data = new float[m0.length][measureResults.size()];
		for (int i = 0; i < measureResults.size(); i++) {
			float[] m = measureResults.get(i);
			for (int j = 0; j < m.length; j++) {
				data[j][i] = m[j];
			}
		}

		String colnames[] = new String[varnames.length + 1];
		colnames[0] = "id";
		for (int i = 0; i < varnames.length; i++) {
			colnames[i + 1] = varnames[i];
		}
		String ids[] = flowD.getIDs();
		String rownames[] = new String[ids.length];
		for (int i = 0; i < rownames.length; i++) {
			// zeros in the beginning of id get omitted
			// here we add them back
			if (ids[i].split("-")[0].length() == 1)
				rownames[i] = "0" + ids[i];
			else
				rownames[i] = ids[i];
		}
//		ReadCSVFile.writeToCSV(colnames, rownames, data, outputFile);
		this.writeCSVInString(colnames, rownames, data);
	}
	
	public ArrayList<float[]> getMeasureResults() {
		return measureResults;
	}

	public void writeCSVInString(String colNames[], String[] rowNames, float[][] data) {
		String outputStr = "";
		try {
			String dataStr = "";
			if (colNames != null) {
				dataStr = colNames[0];
				for (int c = 1; c < colNames.length; c++) {
					dataStr = dataStr + "," + colNames[c];
				}
				dataStr = dataStr + "\n";
			}

			if (data == null) {
				return;
			}

			for (int r = 0; r < data.length; r++) {
				if (rowNames != null)
					dataStr = rowNames[r] + "," + data[r][0];
				else
					dataStr = data[r][0] + "";
				for (int c = 1; c < data[0].length; c++) {
					dataStr = dataStr + "," + data[r][c];
				}
				dataStr = dataStr + "\n";
				outputStr = outputStr + dataStr;
			}
		} catch (Exception ee) {
			ee.printStackTrace();
		}
		this.outputString = outputStr;
	}

}
