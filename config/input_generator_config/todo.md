# working notes....
alright what do we need to do here.
need to get the benchmark jobs started
and need to compare my work with Kimberley's
and need to get the gas and noconf jobs that failed restarted.

That's all we need to do, it's feasible to do that tonight if we take heart

benchmark jobs
check what the default orca on the HPC is
alright no path we just use "orca"

alright, we've got all the DFT done for the benchmark jobs
need to run the coupled cluster jobs as well.

ooh man it's taking a minute to overwrite these isnt it?

alright we got everything set up.
Only thing I wanna do is get rid of all the CO2 jobs from the benchmark.
then we compare work and restart old jobs.

alright, add molecule filter to ccgen.
when in add_molecules have "exclude" filter, which is a regex (no just a string for now)
and "include_only", but we'll do that later
let's see if this works.
alright, after this we'll speedrun the others
ideally asleep around 2.
I'll get some chances to nap throughout the day.
I harmed myself by looking at youtube when I got overwhelmed. It gets me nowhere and I need
to keep the good commitments I make

these aren't running, I don't know why.
she used Tightscf instead of verytight, should I copy?
she also used UHF, this is wrong and might cause an error

alright, I don't want to be difficult. I've done everything the way it is for hers,
just... feel weird using UHF instead of UKS. I think that's wrong...
I don't think it has the same implementation...
or they're just the same? it seem ambiguous in the documentation

alright, hopefully this works.
I should have spent my time on this from the beginning and not on a lot of stuff that didn't really matter
and wasn't what needed to be done.
oh well.
I'll learn for next time.
I can have these run by tomorrow morning, and I should be able to adapt the old script for them.

what else do I need to do?

alright, we're going.
I'll have to whip up the script to visualize the output during the group meeting tomorrow.


documentation says they're synonyms. I'll go by that...
and just do what she did, because it will be easier for her to write up.
I don't think it matters.

-----------------BENCHMARK DONE FOR TONIGHT--------------------------------------------------------------
wait one thing she used m06+ geometries.
I need to start over and do that.
alright.

DONE



------------------COMPARING DATA----------------------------------------------
alright, first thing - need to see the format Kimberley has her data in.
We want to compare...
so in hers, she has...
energy (in hartree and kcal/mol in separate columns)
enthalpy (in hartree and kcal/mol in separate columns)
gibbs (in hartree and kcal/mol in separate columns)

and these are all kinda loosely distributed, under banners with the lavbel of the reactions
the categories:
these are indexed from 1 -8 for c-f and 1-7 for cc
(if we use code, probably do a .tolower() on these
PFOS-8 protonated C-C Fragmentations <N>
    PFOS-8-Protonated   | corresponds to _water_0_1_HSO3_CF2_7_CF3
    Rf <8-N>            | corresponds to _water_0_2_CF3_CF2_{7-N} 
    sulfonic radical    | corresponds to _water_0_2_HSO3_CF2_{N-1}_CF2
PFOS-8 protonated C-F fragmentations <N>
    PFOS-8-Protonated   | corresponds to _water_0_1_HSO3_CF2_7_CF3
    Rf <N>              | corresponds to _water_0_2_HSO3_CF2_{N-1}_CF_CF2_{7-N}_CF3 (for N=8: _water_0_2_CF3_CF2_{7})
    florine radical     | corresponds to _water_0_2_f
<!-- FOR THE REST OF THESE, I FIGURE THE LLM CAN INTERPOLATE THE PATTERN-->
PFOS-8 deprotonated C-C fragmentations <N> 
PFOS-8 deprotonated C-F fragmentations <N>
PFOS-8 radical anion C-C fragmentations <N>
PFOS-8 radical anion C-F fragmentations <N>
PFOS-8 radical dianion C-C Fragmentations <N>
PFOS-8 radical dianion C-F fragmentations <N>

ALRIGHT, feeding this description and the excel file itself to the LLM should be enough for it to convert.
need to load my data into a .csv file as well.


REALIZATION
c-f bdes are indexed up to 8, we only show 7. this is wrong
we should implement alias lists for our parsing scripts, that would be helpful\
really, we can have the alias written to the CSV file we make from these

need to read all the reaction energies into a csv
and need to read all the individual molecule energies into a csv

we probably get by with just G
but we should include H as well..
she also has delta E, (but not singlepoint E)
and electronic, and whatever she has on hers
let's just do G (H and E upon request)


--------------------GAS BDES --------------------------------------------
definitely should do these overnight.
really close to having all the data for them and it's interesting....

could also run the noconf gas bdes overnight as well

---------------------MICHAEL JOBS-------------------------------------------
one more thing-run the jobs for michael as well.
I got chemdraw on this thing?

