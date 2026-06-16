To work on in the pipeline

1) Defining what we download - currently we are seeing scenes being downloaded and processed with no relation to the training data. ( A small sliver of imagery far from where we need it)
This may be due to the way that we define the AOI with padding and then intersect it to see what images we need. -> We need a better rule for that. So maybe how much of the padded area is enclosed by the image (a percentage) and then above that threshold we process and download the image. ****Has been Implemented ***



2) The Durban scenes are out of sync we have some scenes with little to no coverage of the AOI processed 



3) For some scenes the textural features ect have not been processed properly (so only a small section of the image) and the rest is 0 or no data this is not correct for all the data we have we need to have those features as well




4) keeping track of plastic collections over dates so we can create more training data. We should download the minimum amount of planet data possible to allow for us to track the collections across time (so from one to the next)

For example in that Gahna Scene (just to mention 1 instance) the plastic is visble in the planet scenes from 26th October to the 3rd of November. We are only capturing it at one point currently - if we were able to track it across all of the dates with planet - SAR - planet -SAR over this dates this could be very valuable.  