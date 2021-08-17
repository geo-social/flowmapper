package spatialAnalysis;

public class ModularityFlows {

	private String origin;
	public String getOrigin() {
		return origin;
	}

	public void setOrigin(String origin) {
		this.origin = origin;
	}

	public String getDestination() {
		return destination;
	}

	public void setDestination(String destination) {
		this.destination = destination;
	}

	public double getModularity() {
		return modularity;
	}

	public void setModularity(double modularity) {
		this.modularity = modularity;
	}

	public double getRawvolume() {
		return rawvolume;
	}

	public void setRawvolume(double rawvolume) {
		this.rawvolume = rawvolume;
	}

	public double getExpectation() {
		return expectation;
	}

	public void setExpectation(double expectation) {
		this.expectation = expectation;
	}

	private String destination;
	private double modularity;
	private double rawvolume;
	private double expectation;

	public ModularityFlows(String origin, String destination, double modularity, double rawvolume, double expectation) {
		this.origin = origin;
		this.destination = destination;
		this.modularity = modularity;
		this.rawvolume = rawvolume;
		this.expectation = expectation;
	}
}
